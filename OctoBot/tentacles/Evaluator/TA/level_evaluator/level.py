import octobot_evaluators.evaluators as evaluators
import octobot_trading.api as trading_api
import octobot_commons.constants as commons_constants
import octobot_evaluators.util as evaluators_util

class LevelEvaluator(evaluators.TAEvaluator):
    
    def __init__(self, tentacles_setup_config):
        super().__init__(tentacles_setup_config)
        self.level = {}
        self.lastPrize = []
        self.config_time_frames = ["4h","1h","30m"]
    
    """
    ohlcv_callback

    esta funcion es la que nos da los datos de mercado por timeframe
    para poder evaluarlo y dar un resultado en base a esto,
    para ello primeramente hacemos una distincion por timeframe.

    Esta distincion viene dada a que si el timeframe dado es 1m lo unico que queremos
    es la ultima vela cerrada para obtener un "precio en tiempo real", tal vez 
    sería interesante implementar para este timeframe en vez de get_symbol_close_candles
    otra que nos de una aproximación mas en tiempo real.

    Si el timeframe no es 1min lo que hacemos es crear o actualizar el array de niveles
    del timeframe

    Por ultimo una vez hecho esto mediante evaluate terminamos la evaluacion
    """
    async def ohlcv_callback(self, exchange: str, exchange_id: str,
                             cryptocurrency: str, symbol: str, time_frame, candle, inc_in_construction_data):
        
        candle_data = trading_api.get_symbol_close_candles(self.get_exchange_symbol_data(exchange, exchange_id, symbol),
                                                           time_frame,
                                                           include_in_construction=inc_in_construction_data)
        if(time_frame in self.config_time_frames):
            self.logger.info(f"EJECUTANDO CREATE ARRAY LEVEL EN TIMEFRAME -> " + str(time_frame))
            await self.create_array_level(candle_data)
        else:
            self.lastPrize = candle_data
            self.lastPrize = self.lastPrize[::-1][0]
        await self.evaluate(cryptocurrency, symbol, time_frame, candle)
    
    """
    create_array_level

    genera un array de los distintos niveles.
    Por lo que organizamos las velas cerradas del timeframe y vamos comparando vela por vela, 
    de tal forma que si el precio2 comparado es menor igual al precio1 comparado + precio1 comparado * (PARAM_CONFIG)
        (siendo PARAM_CONFIG un parametro de configuracion que nos dara el nivel de detalle 
        para que ese rango sea considerado un nivel.)
    es considerado un precio cercano al precio1 lo que es un nivel y lo añadimos a support.
    si esto no se cumple recogemos lo
    """
    async def create_array_level(self,data):
        data.sort()
        i=0
        d=True
        avg_level_per_time_frame = []
        while d:
            levels = []
            for d1 in data:
                for d2 in data:
                    if d2 <= d1+d1*(0.004) :
                        levels.append(d2)
                        i=i+1
                    else:
                        break
                break
            avg_level_per_time_frame.append(await self.create_avg_level(levels))
            data = data[i:]
            i=0
            if(len(data)==0):
                d = False
        self.logger.info(f"EL TIME FRAME VALUE EN SELF LEVEL ES  -> " + str(self.time_frame.value))
        self.logger.info(f"EL SELF LEVEL ES  -> " + str(self.level))
        self.level = await self.compute_avg_levels(avg_level_per_time_frame)
        self.logger.info(f"TRAS ACTUALIZACION EL SELF LEVEL ES  -> " + str(self.level))
    
    """
    create_level

    llamado desde la funcion create_array_level, 
    esta funcion recibe un array de niveles que estan muy parejos entre si,
    por lo que se deduce que es un area muy pequeña y que podemos generar un nivel
    con ella.

    devolvemos un dict con:
        level: el nivel medio deducido
        count: las veces uqe se ha apsado por ese nivel
        timeframe: el timeframe
    """
    async def create_avg_level(self,data):
        sum = 0
        i=0
        for d in data:
            i=i+1
            sum += d
        len_data = len(data)
        if(len_data>0):
            return {"level":round(sum / len_data,2),"count":i,"timeframe":self.time_frame}
        else:
            return {"level":0,"count":0,"timeframe":self.time_frame}
    
    """
    compute_avg_levels

    una vez tenemos los distintos niveles, cogemos los 3 niveles que más se tocan
    de tal forma que conformamos 3 areas a tener en cuenta en el timeframe
    dando resultado a un array de 3 arrays de niveles, en cada array de niveles
    habrá uno de los niveles que más se toca, junto con su nivel superior e inferior
    si tuviesen.

    seria buento que el numero de niveles que cogemos, que ahora es 3,
    fuese otro parametro de configuracion
    """
    async def compute_avg_levels(self,levels):
        aux_array_sorted = sorted(levels, key=lambda d: d['count'],reverse=True)[:3]
        
        level_composed = []
        for level1 in aux_array_sorted:
            i=0
            med_support = []
            for level2 in levels:
                if(level1["count"]==level2["count"]):
                    if(i==0 and len(levels)==1):
                        med_support.append(level1)
                    elif(i==0 and len(levels)>1):
                        med_support.append(level1)
                        med_support.append(levels[i+1])
                    elif (i>0 and i==len(levels)-1):
                        med_support.append(level1)
                        med_support.append(levels[i-1])
                    else:
                        med_support.append(levels[i-1])
                        med_support.append(level1)
                        med_support.append(levels[i+1])
                i=i+1
            level_composed.append(med_support)
        return level_composed
    
    """
    evaluate

    ultimo paso del evaluador,
    completamos la evaluación, dando a eval_note un valor, 
    siendo esta evaluacion un dict:
        el valor del timeframe: con el array de niveles
        last_prize: el ultimo precio
    """
    async def evaluate(self, cryptocurrency, symbol, time_frame, candle):
        self.eval_note = commons_constants.START_PENDING_EVAL_NOTE
        self.eval_note = {time_frame:self.level,"last_prize":self.lastPrize}
        await self.evaluation_completed(cryptocurrency, symbol, time_frame,
                                        eval_time=evaluators_util.get_eval_time(full_candle=candle,
                                                                                time_frame=time_frame))
    
    @classmethod
    def get_is_symbol_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not symbol dependant else False
        """
        return False

    @classmethod
    def get_is_time_frame_wildcard(cls) -> bool:
        """
        :return: True if the evaluator is not time_frame dependant else False
        """
        return False
