LevelStrategyEvaluator

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

_compute_final_levels

    Esta función basicamente nos actualiza los niveles dados.

_eval_situation

    Primeramente en base a los timeframes,
    cogemos logs para ver como van los distintos niveles y el ultimo precio
    todo esto solo por tener info

    Luego miramos si tenemos un last_prize para asi, poder evaluarlo,
    de tal forma que evaluamos el precio en los distintos niveles de los distintos timeframes
    y damos a self.eval_note un valor

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

_eval_situation_per_value_level

    Aqui lo que hacemos es tenemos un last prize que esta cercano a uno de los niveles
    de un array de niveles, como cada nivel es un dict, que tiene un count, que es las veces
    que se ha tocado ese nivel basicamente hacemos una regla que es 
    si el nivel superior se ha tocado mas veces que el inferior compra, sino vende
    y retornamos un dict, con el nivel que se ha tocado o que es muy cercano y su level sup e inf
    con una evaluacion

_refresh_evaluations
    
    Aquie lo que hacemos es un refresh evaluation de los datos obtenidos por el evaluador

    self.weights_and_period_eval => se inicializa como array vacio pero luego cuando llamamos
        a _register_time_frame() le pasamos el TimeFrame que hayamos definido y un objeto tipo
        SignalWithWeight 
    
    Entonces por cada evaluacion en self.weights_and_period_eval lo pasamos al refresh_evaluation
    pero de la clase SignalWithWeight

_refresh_last_prize
    
    Lo mismo que _refresh_evaluations, pero aqui basicamente es que cogemos el valor de last prize 
    del timeframe de un minuto nada mas

_get_tentacle_registration_topic

    rellenamos self.weights_and_period_evals llamando a la fx _register_time_frame pasandole el timeframe
