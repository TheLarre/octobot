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
import octobot_commons.constants as commons_constants
import octobot_commons.enums as commons_enums
import octobot_evaluators.evaluators as evaluators
import octobot_evaluators.enums as enums
import tentacles.Evaluator.TA as TA
import octobot_evaluators.api.matrix as evaluators_api
import octobot_evaluators.enums as evaluators_enums
import octobot_trading.api as trading_api
import octobot_evaluators.matrix as matrix
import octobot_evaluators.errors as errors
import octobot_evaluators.evaluators.channel as evaluators_channel
"""
  "required_time_frames" : ["1m", "5m", "15m","30m","1h"],
"""
class LevelStrategyEvaluator(evaluators.StrategyEvaluator):

    """
    get_name():
    Tentacle name based on class name
    :return: the tentacle name
    """ 
    "LA SEÑAL NOS LA DA EL NIVEL SUPPORT/RESISTENCIA"
    SIGNAL_CLASS_NAME = TA.LevelEvaluator.get_name()
    SHORT_PERIOD_WEIGHT = 4
    MEDIUM_PERIOD_WEIGHT = 3
    LONG_PERIOD_WEIGHT = 2


    def __init__(self, tentacles_setup_config):
        super().__init__(tentacles_setup_config)
        self.evaluation_last_prize_time_frames = [commons_enums.TimeFrames.ONE_MINUTE.value]
        self.weights_and_period_evals = []
        self.level = []
        self.last_prize = None
        self.config_time_frames = ["4h","1h","30m"]
        self.result_eval_situation_per_timeframe=[]
    
    def init_user_inputs(self, inputs: dict) -> None:
        """
        Called right before starting the tentacle, should define all the tentacle's user inputs unless
        those are defined somewhere else.
        """
        pass

    def get_full_cycle_evaluator_types(self) -> tuple:
        # returns a tuple as it is faster to create than a list
        return enums.EvaluatorMatrixTypes.TA.value, enums.EvaluatorMatrixTypes.SCRIPTED.value
    
    """
    matrix_callback

    Una vez que el evaluador ha completado la evaluación 
    dando valor a su eval_note matrix_callback, nos da
    vía TA_by_timeframe, el resultado del evaluador, por lo que
    si el timeframe es de un minuto lo que hacemos es resfrescar el
    precio, ya que este timeframe nos da el valor "en tiempo real"

    sino es un timeframe de un minuto lo que hacemos es refrescar la evaluacion
    del timeframe que al fin y al cabo son los niveles y posteriormente computar
    estos niveles

    por ultimo finalizamos la estrategia
    """
    async def matrix_callback(self,
                              matrix_id,
                              evaluator_name,
                              evaluator_type,
                              eval_note,
                              eval_note_type,
                              exchange_name,
                              cryptocurrency,
                              symbol,
                              time_frame):
                              
        if evaluator_type == evaluators_enums.EvaluatorMatrixTypes.REAL_TIME.value:
            # trigger re-evaluation
            exchange_id = trading_api.get_exchange_id_from_matrix_id(exchange_name, matrix_id)
            await evaluators_channel.trigger_technical_evaluators_re_evaluation_with_updated_data(matrix_id,
                                                                                                  evaluator_name,
                                                                                                  evaluator_type,
                                                                                                  exchange_name,
                                                                                                  cryptocurrency,
                                                                                                  symbol,
                                                                                                  exchange_id,
                                                                                                  self.strategy_time_frames)
            # do not continue this evaluation
            return
        elif evaluator_type == evaluators_enums.EvaluatorMatrixTypes.TA.value:
            try:
                TA_by_timeframe = {
                    available_time_frame: matrix.get_evaluations_by_evaluator(
                        matrix_id,
                        exchange_name,
                        evaluators_enums.EvaluatorMatrixTypes.TA.value,
                        cryptocurrency,
                        symbol,
                        available_time_frame.value,
                        allow_missing=False,
                        allowed_values=[commons_constants.START_PENDING_EVAL_NOTE])
                    for available_time_frame in self.strategy_time_frames
                }
                
                if(time_frame in self.evaluation_last_prize_time_frames):
                    self._refresh_last_prize(TA_by_timeframe,time_frame)
                else:
                    self._refresh_evaluations(TA_by_timeframe)
                    self._compute_final_levels()
                self._eval_situation(self.level,self.last_prize,time_frame)

                await self.strategy_completed(cryptocurrency, symbol)

            except errors.UnsetTentacleEvaluation as e:
                self.logger.debug(f"Tentacles evaluation initialization: not ready yet for a strategy update ({e})")
            except KeyError as e:
                self.logger.exception(e, True, f"Missing {e} evaluation in matrix for {symbol} on {time_frame}, "
                                      f"did you activate the required evaluator ?")
   
    """
    _compute_final_levels

    Esta función basicamente nos actualiza los niveles dados.
    """
    def _compute_final_levels(self):
        self.level=[]
        for _, evaluation in self.weights_and_period_evals:
            self.level.append(evaluation.signal)

    """
    _eval_situation

    Primeramente en base a los timeframes,
    cogemos logs para ver como van los distintos niveles y el ultimo precio
    todo esto solo por tener info

    Luego miramos si tenemos un last_prize para asi, poder evaluarlo,
    de tal forma que evaluamos el precio en los distintos niveles de los distintos timeframes
    y damos a self.eval_note un valor
    """     
    def _eval_situation(self,levels,last_prize,time_frame):
        self.result_eval_situation_per_timeframe=[]
        if time_frame in  self.config_time_frames:
            self.logger.info(f"BLANK STRATEGY: El nivel en 30m es: -> [{levels[0]}]")
            self.logger.info(f"BLANK STRATEGY: El nivel en 1h es: -> [{levels[1]}]")
            self.logger.info(f"BLANK STRATEGY: El nivel en 4h es: -> [{levels[2]}]")
            self.logger.info(f"BLANK STRATEGY: El last prize es : -> [{last_prize}]")
        if last_prize != None :
            for levels_in_time_frame in levels:
                level_values = list (levels_in_time_frame.values())[0]
                self._eval_situation_per_timeframe(level_values,last_prize)
            self.logger.info(f"EL LAST PRIZE -> " +str(last_prize))
            self.logger.info(f"EL RESULT EVAL SITUATION PER TIMEFRAME ->" +str(self.result_eval_situation_per_timeframe))
        self.eval_note = self.result_eval_situation_per_timeframe
    
    """
    _eval_situation_per_timeframe

    Evaluamos el ultimo precio en los distintos niveles de los distintos timeframes
    para ello, lo que hacemos es coger el array de niveles compuestos,
    este array de niveles compuestos, recordar, que es un array que recoge los niveles mas tocados
    juntos con sus niveles superiores e inferiores
        level_values = [[1,2,3],[4,5,6],[7,8,9]]
    Para tener un mejor acercamiento a si el precio esta tocando algunos de los niveles,
    recorremos todos los niveles y creamos un area para ver si el precio esta cercano a ese nivel
    para tener el area lo q hacemos es:
        level_inf = level["level"] - level["level"]*0.001
        level_sup = level["level"] + level["level"]*0.001
        **EL 0.001 PODRIA SER UN PARAM_CONFIG**
    Por ultimo si el precio esta comprendido en esa area de nivel cogemos el array de niveles,
    por ejemplo tenemos el last_prize 2.1, este precio esta comprendido en el area dada por el nivel 2
    de level_values que hemos puesto como ejemplo posteriormente.
    Por lo que cogemos el array de niveles que guarda ese level, osea el array [1,2,3]
    """   
    def _eval_situation_per_timeframe(self,level_values,last_prize): 
        for array_level in level_values:
            i = 0
            for level in array_level:
                level_inf = level["level"] - level["level"]*0.001
                level_sup = level["level"] + level["level"]*0.001
                if last_prize > level_inf and last_prize < level_sup:
                    self.result_eval_situation_per_timeframe.append(self._eval_situation_per_value_level(level,array_level,i))
                else:
                    i = i+1        
    """
    _eval_situation_per_value_level

    Aqui lo que hacemos es tenemos un last prize que esta cercano a uno de los niveles
    de un array de niveles, como cada nivel es un dict, que tiene un count, que es las veces
    que se ha tocado ese nivel basicamente hacemos una regla que es 
    si el nivel superior se ha tocado mas veces que el inferior compra, sino vende
    y retornamos un dict, con el nivel que se ha tocado o que es muy cercano y su level sup e inf
    con una evaluacion
    """
    def _eval_situation_per_value_level(self,level_value,levels_value,i):
        level_sup = None
        level_inf = None
        evaluation = None
        if(i == 0 and len(levels_value)>1):
            level_sup = levels_value[i+1]
            if(level_value["count"]>=level_sup["count"]):
                self.logger.info(f"NEUTRAL")
                evaluation = "NEUTRAL"
            else:
                self.logger.info(f"LONG")
                evaluation = "LONG"
        elif (i == len(levels_value)-1 and len(levels_value)>1):
            level_inf = levels_value[i-1]
            if(level_value["count"]>=level_inf["count"]):
                self.logger.info(f"NEUTRAL")
                evaluation = "NEUTRAL"
            else:
                self.logger.info(f"SHORT")
                evaluation = "SHORT"
        elif(len(levels_value)>2): 
            level_sup = levels_value[i+1]
            level_inf = levels_value[i-1]
            if(level_value["count"]>=level_sup["count"] and level_value["count"]>=level_inf["count"] and level_sup["count"]>level_inf["count"]):
                self.logger.info(f"NEUTRAL-LONG")
                evaluation = "NEUTRAL-LONG"
            elif(level_value["count"]>=level_sup["count"] and level_value["count"]>=level_inf["count"] and level_sup["count"]<level_inf["count"]):
                self.logger.info(f"NEUTRAL-SHORT")
                evaluation = "NEUTRAL-SHORT"
            elif(level_value["count"]>=level_sup["count"] and level_value["count"]<level_inf["count"]):
                self.logger.info(f"SHORT")
                evaluation = "SHORT"
            elif(level_value["count"]<level_sup["count"] and level_value["count"]>=level_inf["count"]):
                self.logger.info(f"LONG")
                evaluation = "LONG"
            elif(level_value["count"]<=level_sup["count"] and level_value["count"]<=level_inf["count"] and level_sup["count"]>level_inf["count"]):
                self.logger.info(f"NEUTRAL-LONG")
                evaluation = "NEUTRAL-LONG"
            elif(level_value["count"]<=level_sup["count"] and level_value["count"]<=level_inf["count"] and level_sup["count"]<level_inf["count"]):
                self.logger.info(f"NEUTRAL-SHORT")
                evaluation = "NEUTRAL-SHORT"
            else:
                self.logger.info(f"NEUTRAL")
                evaluation = "NEUTRAL"
        else:
            evaluation = "NEUTRAL"
        return {"level_value":level_value,"level_sup":level_sup,"level_inf":level_inf,"evaluation":evaluation}
    
    """
    _refresh_evaluations
    
    Aquie lo que hacemos es un refresh evaluation de los datos obtenidos por el evaluador

    self.weights_and_period_eval => se inicializa como array vacio pero luego cuando llamamos
        a _register_time_frame() le pasamos el TimeFrame que hayamos definido y un objeto tipo
        SignalWithWeight 
    
    Entonces por cada evaluacion en self.weights_and_period_eval lo pasamos al refresh_evaluation
    pero de la clase SignalWithWeight
    """
    def _refresh_evaluations(self, TA_by_timeframe):
        for _, evaluation in self.weights_and_period_evals:
            evaluation.refresh_evaluation(TA_by_timeframe)

    """
    _refresh_last_prize
    
    Lo mismo que _refresh_evaluations, pero aqui basicamente es que cogemos el valor de last prize 
    del timeframe de un minuto nada mas
    """
    def _refresh_last_prize(self, TA_by_timeframe,time_frame):
        for enum, _ in TA_by_timeframe.items():
            if (enum.value == time_frame):
                self.last_prize = TA_by_timeframe[enum][LevelStrategyEvaluator.SIGNAL_CLASS_NAME].node_value["last_prize"]

    """
    _get_tentacle_registration_topic

    rellenamos self.weights_and_period_evals llamando a la fx _register_time_frame pasandole el timeframe
    """
    def _get_tentacle_registration_topic(self, all_symbols_by_crypto_currencies, time_frames, real_time_time_frames):
        currencies, symbols, time_frames = super()._get_tentacle_registration_topic(all_symbols_by_crypto_currencies,
                                                                                    time_frames,
                                                                                    real_time_time_frames)
        # register evaluation fractals based on available time frames
        self._register_time_frame(commons_enums.TimeFrames.THIRTY_MINUTES, self.SHORT_PERIOD_WEIGHT)
        self._register_time_frame(commons_enums.TimeFrames.ONE_HOUR, self.MEDIUM_PERIOD_WEIGHT)
        self._register_time_frame(commons_enums.TimeFrames.FOUR_HOURS, self.LONG_PERIOD_WEIGHT)
        return currencies, symbols, time_frames
        
    def _register_time_frame(self, time_frame, weight):
        if time_frame in self.strategy_time_frames:
            self.weights_and_period_evals.append((weight,
                                                  SignalWithWeight(time_frame)))
        else:
            self.logger.warning(f"Missing {time_frame.value} time frame on {self.exchange_name}, "
                                f"this strategy will not work at its optimal potential.")

"""
COMO ESTAMOS UTILIZANDO UNA SEÑAL QUE SERÁN NUESTROS NIVELES DE SUPPORT Y RESISTANCE
Y LUEGO UN PESO BASADO EN LAS BANDAS DE BOLLINGER CREAMOS UNA CLASE SEÑAL CON PESO
DONDE TENDRA UN TIMEFRAME UNA SEÑAL Y UN PESO QUE EN UN PRINCIPIO SERÁ 0 HASTA QUE SE LLAME
A refresh_evaluation QUE NOS DARÁ EL VALOR DE LAS SEÑALES QUE EN ESTE CASO NOS DE 
LEVELEVALUATOS POR TIMEFRAME Y BBOLINGEREVALUATOR POR TIMEFRAME
"""
class SignalWithWeight:

    def __init__(self, time_frame):
        self.time_frame = time_frame
        self.signal = commons_constants.START_PENDING_EVAL_NOTE
        self.weight = commons_constants.START_PENDING_EVAL_NOTE

    def reset_evaluation(self):
        self.signal = commons_constants.START_PENDING_EVAL_NOTE
        self.weight = commons_constants.START_PENDING_EVAL_NOTE

    def refresh_evaluation(self, TA_by_timeframe):
        self.reset_evaluation()
        self.signal = evaluators_api.get_value(
            TA_by_timeframe[self.time_frame][LevelStrategyEvaluator.SIGNAL_CLASS_NAME])
