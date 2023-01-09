#  Drakkar-Software OctoBot-Tentacles
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.

import asyncio
import decimal
import math

import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_commons.evaluators_util as evaluators_util
import octobot_commons.pretty_printer as pretty_printer
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_evaluators.api as evaluators_api
import octobot_evaluators.constants as evaluators_constants
import octobot_evaluators.enums as evaluators_enums
import octobot_evaluators.matrix as matrix
import octobot_trading.personal_data as trading_personal_data
import octobot_trading.constants as trading_constants
import octobot_trading.errors as trading_errors
import octobot_trading.modes as trading_modes
import octobot_trading.modes.script_keywords as script_keywords
import octobot_trading.enums as trading_enums
import octobot_trading.api as trading_api


class LarreTradingMode(trading_modes.AbstractTradingMode):

    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        trading_modes.user_select_order_amount(self, inputs)
        """
        Estos self.UI son inputs que pueden ser posteriormente modificados en la GUI
        deben definirse en el .json dentro de la carpeta de config del modo de trading
        """
        self.UI.user_input(
            "profit_percentage", commons_enums.UserInputTypes.FLOAT, 3.0, inputs,
            title="Porcentaje de ganancia para cerrar orden",
        )
        self.UI.user_input(
            "loss_percentage", commons_enums.UserInputTypes.FLOAT, 6.0, inputs,
            title="Porcentaje de perdida para cerrar orden",
        )
    """
    Aqui metemos los tipos de exchange que queremos
    class ExchangeTypes(enum.Enum):
        SPOT = "spot"
        FUTURE = "future"
        MARGIN = "margin"
        UNKNOWN = "unknown"
    """
    @classmethod
    def get_supported_exchange_types(cls) -> list:
        """
        :return: The list of supported exchange types
        """
        return [
            trading_enums.ExchangeTypes.SPOT,
        ]

    """
    La fx get_current_state no tengo ni puta idea de que hace 
    
    Hay que hacer un overwrite de esta funcion, pero es simplemente
    para ver el estado actual del trading mode 

    Retorna esto
    :return: (str, float): (current state description, current state value)

    # producers is the list of producers created by this trading mode
    self.producers = []

    # producers is the list of consumers created by this trading mode
    self.consumers = []
    """
    def get_current_state(self) -> (str, float):
        return super().get_current_state()[0] if self.producers[0].state is None else self.producers[0].state.name, \
               self.producers[0].final_eval

    """
    Tanto get_mode_producer_classes como get_mode_consumer_classes imagino que es para conseguie los modos
    del productor y el consumidor
    """
    def get_mode_producer_classes(self) -> list:
        return [LarreTradingModeProducer]

    def get_mode_consumer_classes(self) -> list:
        return [LarreTradingModeConsumer]

    """
    :return: True if the mode is not symbol dependant else False
    """
    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        return False

class LarreTradingModeConsumer(trading_modes.AbstractTradingModeConsumer):
    """
    A consumer keeps reading from the channel and processes any data passed to it.
    A consumer will start consuming by calling its 'consume' method.
    The data processing implementation is coded in the 'perform' method.
    A consumer also responds to channel events like pause and stop.
    """
    PRICE_KEY = "PRICE"
    VOLUME_KEY = "VOLUME"
    STOP_PRICE_KEY = "STOP_PRICE"
    REDUCE_ONLY_KEY = "REDUCE_ONLY"
    
    def __init__(self, trading_mode):
        super().__init__(trading_mode)

        self.trader = self.exchange_manager.trader

        self.MAX_SUM_RESULT = decimal.Decimal(2)
        """
        STOP LOSS
        """
        self.STOP_LOSS_ORDER_MAX_PERCENT = decimal.Decimal(str(0.99))
        self.STOP_LOSS_ORDER_MIN_PERCENT = decimal.Decimal(str(0.95))
        self.STOP_LOSS_ORDER_ATTENUATION = (self.STOP_LOSS_ORDER_MAX_PERCENT - self.STOP_LOSS_ORDER_MIN_PERCENT)
        """
        CANTIDAD %
        """
        self.QUANTITY_MIN_PERCENT = decimal.Decimal(str(0.1))
        self.QUANTITY_MAX_PERCENT = decimal.Decimal(str(0.9))
        self.QUANTITY_ATTENUATION = (self.QUANTITY_MAX_PERCENT - self.QUANTITY_MIN_PERCENT) / self.MAX_SUM_RESULT
        """
        CANTIDAD MARKET %
        """
        self.QUANTITY_MARKET_MIN_PERCENT = decimal.Decimal(str(0.3))
        self.QUANTITY_MARKET_MAX_PERCENT = decimal.Decimal(str(1))
        self.QUANTITY_BUY_MARKET_ATTENUATION = decimal.Decimal(str(0.2))
        self.QUANTITY_MARKET_ATTENUATION = (self.QUANTITY_MARKET_MAX_PERCENT - self.QUANTITY_MARKET_MIN_PERCENT) \
                                           / self.MAX_SUM_RESULT
        """
        BUY Y SELL ORDER
        """
        self.BUY_LIMIT_ORDER_MAX_PERCENT = decimal.Decimal(str(0.995))
        self.BUY_LIMIT_ORDER_MIN_PERCENT = decimal.Decimal(str(0.98))
        self.SELL_LIMIT_ORDER_MIN_PERCENT = 1 + (1 - self.BUY_LIMIT_ORDER_MAX_PERCENT)
        self.SELL_LIMIT_ORDER_MAX_PERCENT = 1 + (1 - self.BUY_LIMIT_ORDER_MIN_PERCENT)
        self.LIMIT_ORDER_ATTENUATION = (self.BUY_LIMIT_ORDER_MAX_PERCENT - self.BUY_LIMIT_ORDER_MIN_PERCENT) \
                                       / self.MAX_SUM_RESULT
        """
        CANTIDAD DE RIESGO DE PESO
        """
        self.QUANTITY_RISK_WEIGHT = decimal.Decimal(str(0.2))
        self.MAX_QUANTITY_RATIO = decimal.Decimal(str(1))
        self.MIN_QUANTITY_RATIO = decimal.Decimal(str(0.2))
        self.DELTA_RATIO = self.MAX_QUANTITY_RATIO - self.MIN_QUANTITY_RATIO

        # consider a high ratio not to take too much risk and not to prevent order creation either
        self.DEFAULT_HOLDING_RATIO = decimal.Decimal(str(0.35))

        self.SELL_MULTIPLIER = decimal.Decimal(str(5))
        self.FULL_SELL_MIN_RATIO = decimal.Decimal(str(0.05))

        trading_config = self.trading_mode.trading_config if self.trading_mode else {}
        """
        PARAMETROS DE CONFIGURACION CON VALORES INICIALES
        """
        self.USE_CLOSE_TO_CURRENT_PRICE = trading_config.get("use_prices_close_to_current_price", False)
        self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO = decimal.Decimal(str(
            trading_config.get("close_to_current_price_difference", 0.02)))
        self.BUY_WITH_MAXIMUM_SIZE_ORDERS = trading_config.get("buy_with_maximum_size_orders", False)
        self.SELL_WITH_MAXIMUM_SIZE_ORDERS = trading_config.get("sell_with_maximum_size_orders", False)
        self.DISABLE_SELL_ORDERS = trading_config.get("disable_sell_orders", False)
        self.DISABLE_BUY_ORDERS = trading_config.get("disable_buy_orders", False)
        self.USE_STOP_ORDERS = trading_config.get("use_stop_orders", True)
        self.MAX_CURRENCY_RATIO = trading_config.get("max_currency_percent", None)
        if self.MAX_CURRENCY_RATIO is not None:
            self.MAX_CURRENCY_RATIO = decimal.Decimal(str(self.MAX_CURRENCY_RATIO)) / trading_constants.ONE_HUNDRED

    def flush(self):
        super().flush()
        self.trader = None
    """
    GET LIMIT PRICE FROM RISK
    EVALUACION DEL LIMITE DE PRECIO DE COMPRA O VENTA 
    DEPENDIENDO DE LA NOTA DE EVALUACION
    """
    """
    Starting point : self.SELL_LIMIT_ORDER_MIN_PERCENT or self.BUY_LIMIT_ORDER_MAX_PERCENT
    1 - abs(eval_note) --> confirmation level --> high : sell less expensive / buy more expensive
    1 - trader.risk --> high risk : sell / buy closer to the current price
    1 - abs(eval_note) + 1 - trader.risk --> result between 0 and 2 --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.XXX_MIN_PERCENT and self.XXX_MAX_PERCENT
    """
    def _get_limit_price_from_risk(self, eval_note):
        if eval_note > 0:
            if self.USE_CLOSE_TO_CURRENT_PRICE:
                return 1 + self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO
            factor = self.SELL_LIMIT_ORDER_MIN_PERCENT + \
                     ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return trading_modes.check_factor(self.SELL_LIMIT_ORDER_MIN_PERCENT,
                                              self.SELL_LIMIT_ORDER_MAX_PERCENT, factor)
        else:
            if self.USE_CLOSE_TO_CURRENT_PRICE:
                return 1 - self.CLOSE_TO_CURRENT_PRICE_DEFAULT_RATIO
            factor = self.BUY_LIMIT_ORDER_MAX_PERCENT - \
                     ((1 - abs(eval_note) + 1 - self.trader.risk) * self.LIMIT_ORDER_ATTENUATION)
            return trading_modes.check_factor(self.BUY_LIMIT_ORDER_MIN_PERCENT,
                                              self.BUY_LIMIT_ORDER_MAX_PERCENT, factor)
    
    """
    GET STOP PRICE FROM RISK
    STOP LOSS
    """
    """
    Starting point : self.STOP_LOSS_ORDER_MAX_PERCENT
    trader.risk --> low risk : stop level close to the current price
    self.STOP_LOSS_ORDER_ATTENUATION --> try to contains the result between self.STOP_LOSS_ORDER_MIN_PERCENT
    and self.STOP_LOSS_ORDER_MAX_PERCENT
    """
    def _get_stop_price_from_risk(self, is_long):
        max_percent = self.STOP_LOSS_ORDER_MAX_PERCENT if is_long \
            else 2 * trading_constants.ONE - self.STOP_LOSS_ORDER_MIN_PERCENT
        min_percent = self.STOP_LOSS_ORDER_MIN_PERCENT if is_long \
            else 2 * trading_constants.ONE - self.STOP_LOSS_ORDER_MAX_PERCENT
        risk_difference = self.trader.risk * self.STOP_LOSS_ORDER_ATTENUATION
        factor = max_percent - risk_difference if is_long else min_percent + risk_difference
        return trading_modes.check_factor(min_percent, max_percent, factor)
    
    """
    GET BUY LIMIT QUANTITY FROM RISK
    """
    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    abs(eval_note) + weighted_risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT
    and self.QUANTITY_MAX_PERCENT
    """

    async def _get_buy_limit_quantity_from_risk(self, ctx, eval_note, quantity, quote):
        # check all in orders
        if self.BUY_WITH_MAXIMUM_SIZE_ORDERS:
            return quantity
        # check configured quantity
        if user_amount := trading_modes.get_user_selected_order_amount(self.trading_mode,
                                                                       trading_enums.TradeOrderSide.BUY):
            return await script_keywords.get_amount_from_input_amount(
                context=ctx,
                input_amount=user_amount,
                side=trading_enums.TradeOrderSide.BUY.value,
                reduce_only=False,
                is_stop_order=False,
                use_total_holding=False,
            )
        # get quantity from risk
        max_amount = self._get_max_amount_from_max_ratio(self.MAX_CURRENCY_RATIO, quantity,
                                                         quote, self.QUANTITY_MAX_PERCENT)
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider buy quantity like a sell if quote is the reference market
        if quote == self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
            weighted_risk *= self.SELL_MULTIPLIER
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = trading_modes.check_factor(self.QUANTITY_MIN_PERCENT, self.QUANTITY_MAX_PERCENT,
                                                    factor)
        holding_ratio = self._get_quantity_ratio(quote)
        return min(checked_factor * quantity * holding_ratio, max_amount)

    """
    Starting point : self.QUANTITY_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    use SELL_MULTIPLIER to increase sell volume relatively to risk
    if currency holding < FULL_SELL_MIN_RATIO, sell everything to free up funds
    abs(eval_note) + weighted_risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_ATTENUATION --> try to contains the result between self.QUANTITY_MIN_PERCENT
    and self.QUANTITY_MAX_PERCENT
    """

    async def _get_sell_limit_quantity_from_risk(self, ctx, eval_note, quantity, quote):
        # check all in orders
        if self.SELL_WITH_MAXIMUM_SIZE_ORDERS:
            return quantity
        if user_amount := trading_modes.get_user_selected_order_amount(self.trading_mode,
                                                                       trading_enums.TradeOrderSide.SELL):
            return await script_keywords.get_amount_from_input_amount(
                context=ctx,
                input_amount=user_amount,
                side=trading_enums.TradeOrderSide.SELL.value,
                reduce_only=False,
                is_stop_order=False,
                use_total_holding=False,
            )
        # check configured quantity
        # get quantity from risk
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        # consider sell quantity like a buy if base is the reference market
        if quote != self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market:
            weighted_risk *= self.SELL_MULTIPLIER
        if self._get_ratio(quote) < self.FULL_SELL_MIN_RATIO:
            return quantity
        factor = self.QUANTITY_MIN_PERCENT + ((abs(eval_note) + weighted_risk) * self.QUANTITY_ATTENUATION)
        checked_factor = trading_modes.check_factor(self.QUANTITY_MIN_PERCENT, self.QUANTITY_MAX_PERCENT,
                                                    factor)
        return checked_factor * quantity
    """
    Starting point : self.QUANTITY_MARKET_MIN_PERCENT
    abs(eval_note) --> confirmation level --> high : sell/buy more quantity
    trader.risk --> high risk : sell / buy more quantity
    use SELL_MULTIPLIER to increase sell volume relatively to risk
    abs(eval_note) + trader.risk --> result between 0 and 1 + self.QUANTITY_RISK_WEIGHT --> self.MAX_SUM_RESULT
    self.QUANTITY_MARKET_ATTENUATION --> try to contains the result between self.QUANTITY_MARKET_MIN_PERCENT
    and self.QUANTITY_MARKET_MAX_PERCENT
    """

    async def _get_market_quantity_from_risk(self, ctx, eval_note, quantity, quote, selling=False):
        # check configured quantity
        side = trading_enums.TradeOrderSide.SELL if selling else trading_enums.TradeOrderSide.BUY
        if user_amount := trading_modes.get_user_selected_order_amount(self.trading_mode, side):
            return await script_keywords.get_amount_from_input_amount(
                context=ctx,
                input_amount=user_amount,
                side=side.value,
                reduce_only=False,
                is_stop_order=False,
                use_total_holding=False,
            )
        # get quantity from risk
        max_amount = quantity * self.QUANTITY_MARKET_MAX_PERCENT if selling \
            else self._get_max_amount_from_max_ratio(self.MAX_CURRENCY_RATIO, quantity,
                                                     quote, self.QUANTITY_MARKET_MAX_PERCENT)
        weighted_risk = self.trader.risk * self.QUANTITY_RISK_WEIGHT
        ref_market = self.exchange_manager.exchange_personal_data.portfolio_manager.reference_market
        if (selling and quote != ref_market) or (not selling and quote == ref_market):
            weighted_risk *= self.SELL_MULTIPLIER
        factor = self.QUANTITY_MARKET_MIN_PERCENT + (
                (abs(eval_note) + weighted_risk) * self.QUANTITY_MARKET_ATTENUATION)

        checked_factor = trading_modes.check_factor(self.QUANTITY_MARKET_MIN_PERCENT,
                                                    self.QUANTITY_MARKET_MAX_PERCENT, factor)
        holding_ratio = 1 if selling else self._get_quantity_ratio(quote)
        return min(checked_factor * holding_ratio * quantity, max_amount)

    def _get_ratio(self, currency):
        try:
            return self.get_holdings_ratio(currency)
        except trading_errors.MissingPriceDataError:
            # Can happen when ref market is not in the pair, data will be available later (ticker is now registered)
            return self.DEFAULT_HOLDING_RATIO

    def _get_quantity_ratio(self, currency):
        if self.get_number_of_traded_assets() > 2:
            ratio = self._get_ratio(currency)
            # returns a linear result between self.MIN_QUANTITY_RATIO and self.MAX_QUANTITY_RATIO: closer to
            # self.MAX_QUANTITY_RATIO when holdings are lower in % and to self.MIN_QUANTITY_RATIO when holdings
            # are higher in %
            return 1 - min(ratio * self.DELTA_RATIO, 1)
        else:
            return 1

    def _get_max_amount_from_max_ratio(self, max_ratio, quantity, quote, default_ratio):
        # reduce max amount when self.MAX_CURRENCY_RATIO is defined
        if self.MAX_CURRENCY_RATIO is None or max_ratio == trading_constants.ONE:
            return quantity * default_ratio
        max_amount_ratio = max_ratio - self._get_ratio(quote)
        if max_amount_ratio > 0:
            max_amount_in_ref_market = trading_api.get_current_portfolio_value(self.exchange_manager) * \
                                       max_amount_ratio
            try:
                max_theoretical_amount = max_amount_in_ref_market / trading_api.get_current_crypto_currency_value(
                    self.exchange_manager, quote)
                return min(max_theoretical_amount, quantity)
            except KeyError:
                self.logger.error(f"Missing price information in reference market for {quote}. Skipping buy order "
                                  f"as is it required to ensure the maximum currency percent parameter. "
                                  f"Set it to 100 to buy anyway.")
        return trading_constants.ZERO

    """
    CREACION DE ORDENES
    """
    async def create_new_orders(self, symbol, final_note, state, **kwargs):
        # try:
        #     if final_note.is_nan():
        #         return []
        # except AttributeError:
        #     final_note = decimal.Decimal(str(final_note))
        #     if final_note.is_nan():
        #         return []
        data = kwargs.get("data", {})
        user_price = data.get(self.PRICE_KEY, trading_constants.ZERO)
        user_volume = data.get(self.VOLUME_KEY, trading_constants.ZERO)
        user_reduce_only = data.get(self.REDUCE_ONLY_KEY, False) if self.exchange_manager.is_future else None
        user_stop_price = data.get(self.STOP_PRICE_KEY, decimal.Decimal(math.nan))
        current_order = None
        orders_should_have_been_created = False
        timeout = kwargs.pop("timeout", trading_constants.ORDER_DATA_FETCHING_TIMEOUT)
        ctx = script_keywords.get_base_context(self.trading_mode, symbol)
        try:
            current_symbol_holding, current_market_holding, market_quantity, price, symbol_market = \
                await trading_personal_data.get_pre_order_data(self.exchange_manager, symbol=symbol, timeout=timeout)
            max_buy_size = market_quantity
            max_sell_size = current_symbol_holding
            if self.exchange_manager.is_future:
                # on futures, current_symbol_holding = current_market_holding = market_quantity
                max_buy_size, _ = trading_personal_data.get_futures_max_order_size(
                    self.exchange_manager, symbol, trading_enums.TradeOrderSide.BUY,
                    price, False, current_symbol_holding, market_quantity
                )
                max_sell_size, _ = trading_personal_data.get_futures_max_order_size(
                    self.exchange_manager, symbol, trading_enums.TradeOrderSide.SELL,
                    price, False, current_symbol_holding, market_quantity
                )
            base = symbol_util.parse_symbol(symbol).base
            created_orders = []

            if state == trading_enums.EvaluatorStates.VERY_SHORT.value and not self.DISABLE_SELL_ORDERS:
                self.logger.info(f"LARRE TRADING: Creando orden en VERY SHORT")
                # quantity = user_volume \
                #            or await self._get_market_quantity_from_risk(ctx, final_note, max_sell_size, base, True)
                # quantity = trading_personal_data.decimal_add_dusts_to_quantity_if_necessary(quantity, price,
                #                                                                             symbol_market,
                #                                                                             max_sell_size)
                quantity = decimal.Decimal(float(max_sell_size)*0.15)
                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(trader=self.trader,
                                                                                order_type=trading_enums.TraderOrderType.SELL_MARKET,
                                                                                symbol=symbol,
                                                                                current_price=order_price,
                                                                                quantity=order_quantity,
                                                                                price=order_price,
                                                                                reduce_only=user_reduce_only)
                    if current_order := await self.trading_mode.create_order(current_order):
                        created_orders.append(current_order)

            elif state == trading_enums.EvaluatorStates.SHORT.value and not self.DISABLE_SELL_ORDERS:
                self.logger.info(f"LARRE TRADING: Creando orden en SHORT")
                # quantity = user_volume or \
                #            await self._get_sell_limit_quantity_from_risk(ctx, final_note, max_sell_size, base)
                # quantity = trading_personal_data.decimal_add_dusts_to_quantity_if_necessary(quantity, price, symbol_market,
                #                                                                             max_sell_size)
                quantity = decimal.Decimal(float(max_sell_size)*0.1)
                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(trader=self.trader,
                                                                                order_type=trading_enums.TraderOrderType.SELL_MARKET,
                                                                                symbol=symbol,
                                                                                current_price=order_price,
                                                                                quantity=order_quantity,
                                                                                price=order_price,
                                                                                reduce_only=user_reduce_only)
                    if current_order := await self.trading_mode.create_order(current_order):
                        created_orders.append(current_order)
                # limit_price = trading_personal_data.decimal_adapt_price(symbol_market,
                #                                                         user_price or
                #                                                         (price * self._get_limit_price_from_risk(decimal.Decimal(0.003))))
                # # limit_price = trading_personal_data.decimal_adapt_price(symbol_market,
                # #                                                         user_price or
                # #                                                         (price * self._get_limit_price_from_risk(
                # #                                                             final_note)))                                                           
                # for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                #         quantity,
                #         limit_price,
                #         symbol_market):
                #     orders_should_have_been_created = True
                #     current_order = trading_personal_data.create_order_instance(trader=self.trader,
                #                                                                 order_type=trading_enums.TraderOrderType.SELL_LIMIT,
                #                                                                 symbol=symbol,
                #                                                                 current_price=price,
                #                                                                 quantity=order_quantity,
                #                                                                 price=order_price,
                #                                                                 reduce_only=user_reduce_only)
                #     if updated_limit := await self.trading_mode.create_order(current_order):
                #         created_orders.append(updated_limit)
                #         # ensure stop orders are enabled and limit order was not instantly filled
                #         if (self.USE_STOP_ORDERS or not user_stop_price.is_nan()) and updated_limit.is_open():
                #             oco_group = self.exchange_manager.exchange_personal_data.orders_manager \
                #                 .create_group(trading_personal_data.OneCancelsTheOtherOrderGroup)
                #             updated_limit.add_to_order_group(oco_group)
                #             stop_price = trading_personal_data.decimal_adapt_price(
                #                 symbol_market, price * self._get_stop_price_from_risk(True)
                #             ) if user_stop_price.is_nan() else user_stop_price
                #             current_order = trading_personal_data.create_order_instance(trader=self.trader,
                #                                                                         order_type=trading_enums.TraderOrderType.STOP_LOSS,
                #                                                                         symbol=symbol,
                #                                                                         current_price=price,
                #                                                                         quantity=order_quantity,
                #                                                                         price=stop_price,
                #                                                                         side=trading_enums.TradeOrderSide.SELL,
                #                                                                         reduce_only=True,
                #                                                                         group=oco_group)
                #             await self.trading_mode.create_order(current_order)

            elif state == trading_enums.EvaluatorStates.NEUTRAL.value:
                self.logger.info(f"LARRE TRADING: Sin crear orden por NEUTRAL")
                return []

            elif state == trading_enums.EvaluatorStates.LONG.value and not self.DISABLE_BUY_ORDERS:
                self.logger.info(f"LARRE TRADING: Creando orden en LONG")
                # quantity = await self._get_buy_limit_quantity_from_risk(ctx, final_note, max_buy_size, base) \
                #     if user_volume == 0 else user_volume
                quantity = decimal.Decimal(float(max_buy_size)*0.1)
                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(trader=self.trader,
                                                                                order_type=trading_enums.TraderOrderType.BUY_MARKET,
                                                                                symbol=symbol,
                                                                                current_price=order_price,
                                                                                quantity=order_quantity,
                                                                                price=order_price,
                                                                                reduce_only=user_reduce_only)
                    if current_order := await self.trading_mode.create_order(current_order):
                        created_orders.append(current_order)
                # limit_price = trading_personal_data.decimal_adapt_price(symbol_market,
                #                                                         user_price or
                #                                                         (price * self._get_limit_price_from_risk(decimal.Decimal(0.003))))
                # limit_price = trading_personal_data.decimal_adapt_price(symbol_market,
                #                                                         user_price or
                #                                                         (price * self._get_limit_price_from_risk(
                #                                                             final_note)))
                # for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                #         quantity,
                #         limit_price,
                #         symbol_market):
                #     orders_should_have_been_created = True
                #     current_order = trading_personal_data.create_order_instance(trader=self.trader,
                #                                                                 order_type=trading_enums.TraderOrderType.BUY_LIMIT,
                #                                                                 symbol=symbol,
                #                                                                 current_price=price,
                #                                                                 quantity=order_quantity,
                #                                                                 price=order_price,
                #                                                                 reduce_only=user_reduce_only)
                #     if updated_limit := await self.trading_mode.create_order(current_order):
                #         created_orders.append(updated_limit)
                #         # ensure future trading and stop orders are enabled and limit order was not instantly filled
                #         if self.exchange_manager.is_future and (self.USE_STOP_ORDERS or not user_stop_price.is_nan()) \
                #                 and updated_limit.is_open():
                #             oco_group = self.exchange_manager.exchange_personal_data.orders_manager \
                #                 .create_group(trading_personal_data.OneCancelsTheOtherOrderGroup)
                #             updated_limit.add_to_order_group(oco_group)
                #             stop_price = trading_personal_data.decimal_adapt_price(
                #                 symbol_market, price * self._get_stop_price_from_risk(False)
                #             ) if user_stop_price.is_nan() else user_stop_price
                #             current_order = trading_personal_data.create_order_instance(trader=self.trader,
                #                                                                         order_type=trading_enums.TraderOrderType.STOP_LOSS,
                #                                                                         symbol=symbol,
                #                                                                         current_price=price,
                #                                                                         quantity=order_quantity,
                #                                                                         price=stop_price,
                #                                                                         side=trading_enums.TradeOrderSide.BUY,
                #                                                                         reduce_only=True,
                #                                                                         group=oco_group)
                #             await self.trading_mode.create_order(current_order)

            elif state == trading_enums.EvaluatorStates.VERY_LONG.value and not self.DISABLE_BUY_ORDERS:
                self.logger.info(f"LARRE TRADING: Creando orden en VERY LONG")
                # quantity = await self._get_market_quantity_from_risk(ctx, final_note, max_buy_size, base) \
                #     if user_volume == 0 else user_volume
                quantity = decimal.Decimal(float(max_buy_size)*0.15) 
                for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                        quantity,
                        price,
                        symbol_market):
                    orders_should_have_been_created = True
                    current_order = trading_personal_data.create_order_instance(trader=self.trader,
                                                                                order_type=trading_enums.TraderOrderType.BUY_MARKET,
                                                                                symbol=symbol,
                                                                                current_price=order_price,
                                                                                quantity=order_quantity,
                                                                                price=order_price,
                                                                                reduce_only=user_reduce_only)
                    if current_order := await self.trading_mode.create_order(current_order):
                        created_orders.append(current_order)
                # for order_quantity, order_price in trading_personal_data.decimal_check_and_adapt_order_details_if_necessary(
                #         quantity,
                #         price,
                #         symbol_market):
                #     orders_should_have_been_created = True
                #     current_order = trading_personal_data.create_order_instance(trader=self.trader,
                #                                                                 order_type=trading_enums.TraderOrderType.BUY_MARKET,
                #                                                                 symbol=symbol,
                #                                                                 current_price=order_price,
                #                                                                 quantity=order_quantity,
                #                                                                 price=order_price,
                #                                                                 reduce_only=user_reduce_only)
                #     if current_order := await self.trading_mode.create_order(current_order):
                #         created_orders.append(current_order)
            if created_orders:
                return created_orders
            if orders_should_have_been_created:
                raise trading_errors.OrderCreationError()
            raise trading_errors.MissingMinimalExchangeTradeVolume()

        except (trading_errors.MissingFunds,
                trading_errors.MissingMinimalExchangeTradeVolume,
                trading_errors.OrderCreationError):
            raise
        except asyncio.TimeoutError as e:
            self.logger.error(f"Impossible to create order for {symbol} on {self.exchange_manager.exchange_name}: {e} "
                              f"and is necessary to compute the order details.")
            return []
        except Exception as e:
            self.logger.exception(e, True, f"Failed to create order : {e}.")
            return []

class LarreTradingModeProducer(trading_modes.AbstractTradingModeProducer):

    def __init__(self, channel, config, trading_mode, exchange_manager):
        super().__init__(channel, config, trading_mode, exchange_manager)

        self.state = None

        # If final_eval not is < X_THRESHOLD --> state = X
        self.VERY_LONG_THRESHOLD = decimal.Decimal("-0.85")
        self.LONG_THRESHOLD = decimal.Decimal("-0.25")
        self.NEUTRAL_THRESHOLD = decimal.Decimal("0.25")
        self.SHORT_THRESHOLD = decimal.Decimal("0.85")
        self.RISK_THRESHOLD = decimal.Decimal("0.2")

    async def stop(self):
        if self.trading_mode is not None:
            self.trading_mode.flush_trading_mode_consumers()
        await super().stop()

    async def set_final_eval(self, matrix_id: str, cryptocurrency: str, symbol: str, time_frame):
        
        strategies_analysis_note_counter = 0
        evaluation = commons_constants.INIT_EVAL_NOTE
        # Strategies analysis
        for evaluated_strategy_node in matrix.get_tentacles_value_nodes(
                matrix_id,
                matrix.get_tentacle_nodes(matrix_id,
                                          exchange_name=self.exchange_name,
                                          tentacle_type=evaluators_enums.EvaluatorMatrixTypes.STRATEGIES.value),
                cryptocurrency=cryptocurrency,
                symbol=symbol):

            if evaluators_util.check_valid_eval_note(evaluators_api.get_value(evaluated_strategy_node),
                                                     evaluators_api.get_type(evaluated_strategy_node),
                                                     evaluators_constants.EVALUATOR_EVAL_DEFAULT_TYPE):
                evaluator_data = evaluators_api.get_value(
                    evaluated_strategy_node)
                # evaluation += evaluators_api.get_value(
                #     evaluated_strategy_node)  # TODO * evaluated_strategies.get_pertinence()
                strategies_analysis_note_counter += 1  # TODO evaluated_strategies.get_pertinence()

        if strategies_analysis_note_counter > 0:
            self.final_eval = evaluator_data
            await self.create_state(cryptocurrency=cryptocurrency, symbol=symbol)

    def _get_delta_risk(self):
        return self.RISK_THRESHOLD * self.exchange_manager.trader.risk

    async def create_state(self, cryptocurrency: str, symbol: str):
        self.logger.info(f"LARRE TRADING: La evaluacion final es -> [{self.final_eval}]")
        all_states=[]
        for eval in self.final_eval:
            all_states.append(eval["evaluation"])
        final_state = self._generate_final_state(all_states)
        if final_state == "LONG":
            self.logger.info(f"LARRE TRADING: RESULTADO VERY_LONG")
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.VERY_LONG)
        elif final_state == "NEUTRAL-LONG":
            self.logger.info(f"LARRE TRADING: RESULTADO LONG")
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.LONG)
        elif final_state == "NEUTRAL" or final_state == "":
            self.logger.info(f"LARRE TRADING: RESULTADO NEUTRAL")
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.NEUTRAL)
        elif final_state == "NEUTRAL-SHORT":
            self.logger.info(f"LARRE TRADING: RESULTADO SHORT")
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.SHORT)
        else:
            self.logger.info(f"LARRE TRADING: RESULTADO VERY SHORT")
            await self._set_state(cryptocurrency=cryptocurrency,
                                  symbol=symbol,
                                  new_state=trading_enums.EvaluatorStates.VERY_SHORT)
   
    def _generate_final_state(self,all_states):
        final_state = ""
        for state in all_states:
            if(final_state != ""):
                if (state == "LONG"):
                    if(final_state == "LONG"):
                        break
                    elif (final_state == "NEUTRAL-LONG"):
                        final_state = "LONG"
                        break
                    elif (final_state == "NEUTRAL-SHORT"):
                        final_state = "NEUTRAL"
                        break
                    elif (final_state == "SHORT"):
                        final_state = "NEUTRAL-SHORT"
                        break
                elif (state == "NEUTRAL-LONG"):
                    if(final_state == "LONG"):
                        final_state = "LONG"
                        break
                    elif (final_state == "NEUTRAL-LONG"):
                        break
                    elif (final_state == "NEUTRAL-SHORT"):
                        final_state = "NEUTRAL"
                        break
                    elif (final_state == "SHORT"):
                        final_state = "NEUTRAL"
                        break
                elif (state == "NEUTRAL-SHORT"):
                    if(final_state == "LONG"):
                        final_state = "NEUTRAL"
                        break
                    elif (final_state == "NEUTRAL-LONG"):
                        final_state = "NEUTRAL"
                        break
                    elif (final_state == "NEUTRAL-SHORT"):
                        break
                    elif (final_state == "SHORT"):
                        final_state = "SHORT"
                        break
                elif (state == "SHORT"):
                    if(final_state == "LONG"):
                        final_state = "NEUTRAL"
                        break
                    elif (final_state == "NEUTRAL-LONG"):
                        final_state = "NEUTRAL"
                        break
                    elif (final_state == "NEUTRAL-SHORT"):
                        final_state = "SHORT"
                        break
                    elif (final_state == "SHORT"):
                        break
            else:
                final_state = state
        return final_state
    
    @classmethod
    def get_should_cancel_loaded_orders(cls):
        return True

    async def _set_state(self, cryptocurrency: str, symbol: str, new_state):
        if new_state != self.state:
            self.state = new_state
            self.logger.info(f"LARRE TRADING: [{symbol}] new state: {self.state.name}")

            # if new state is not neutral --> cancel orders and create new else keep orders
            if new_state is not trading_enums.EvaluatorStates.NEUTRAL:
                # cancel open orders
                await self.cancel_symbol_open_orders(symbol)

                # call orders creation from consumers
                await self.submit_trading_evaluation(cryptocurrency=cryptocurrency,
                                                     symbol=symbol,
                                                     time_frame=None,
                                                     final_note=self.final_eval,
                                                     state=self.state)

                # send_notification
                if not self.exchange_manager.is_backtesting:
                    await self._send_alert_notification(symbol, new_state)

    async def _send_alert_notification(self, symbol, new_state):
        try:
            import octobot_services.api as services_api
            import octobot_services.enums as services_enum
            title = f"LARRE TRADING OCTOBOT ALERT : #{symbol}"
            alert_content, alert_content_markdown = pretty_printer.cryptocurrency_alert(
                new_state,
                self.final_eval)
            await services_api.send_notification(services_api.create_notification(alert_content, title=title,
                                                                                  markdown_text=alert_content_markdown,
                                                                                  category=services_enum.NotificationCategory.PRICE_ALERTS))
        except ImportError as e:
            self.logger.exception(e, True, f"Impossible to send notification: {e}")
