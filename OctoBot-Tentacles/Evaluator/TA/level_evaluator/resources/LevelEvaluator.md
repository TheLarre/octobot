Evaluador para detectar los distintos niveles de support y resistencia

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

create_array_level

    genera un array de los distintos niveles.
    Por lo que organizamos las velas cerradas del timeframe y vamos comparando vela por vela, 
    de tal forma que si el precio2 comparado es menor igual al precio1 comparado + precio1 comparado * (PARAM_CONFIG)
        (siendo PARAM_CONFIG un parametro de configuracion que nos dara el nivel de detalle 
        para que ese rango sea considerado un nivel.)
    es considerado un precio cercano al precio1 lo que es un nivel y lo añadimos a support.
    si esto no se cumple recogemos lo

create_level

    llamado desde la funcion create_array_level, 
    esta funcion recibe un array de niveles que estan muy parejos entre si,
    por lo que se deduce que es un area muy pequeña y que podemos generar un nivel
    con ella.

    devolvemos un dict con:
        level: el nivel medio deducido
        count: las veces uqe se ha apsado por ese nivel
        timeframe: el timeframe

compute_avg_levels

    una vez tenemos los distintos niveles, cogemos los 3 niveles que más se tocan
    de tal forma que conformamos 3 areas a tener en cuenta en el timeframe
    dando resultado a un array de 3 arrays de niveles, en cada array de niveles
    habrá uno de los niveles que más se toca, junto con su nivel superior e inferior
    si tuviesen.

    seria buento que el numero de niveles que cogemos, que ahora es 3,
    fuese otro parametro de configuracion

evaluate

    ultimo paso del evaluador,
    completamos la evaluación, dando a eval_note un valor, 
    siendo esta evaluacion un dict:
        el valor del timeframe: con el array de niveles
        last_prize: el ultimo precio