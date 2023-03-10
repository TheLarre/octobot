# cython: language_level=3
#  Drakkar-Software OctoBot
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
cimport octobot.channels as octobot_channel 


cdef class ExchangeProducer(octobot_channel.OctoBotChannelProducer):
    cdef object octobot
    cdef object backtesting

    cdef bint ignore_config

    cdef public list exchange_manager_ids

    cdef int to_create_exchanges_count
    cdef public object created_all_exchanges

    cpdef void register_created_exchange_id(self, str exchange_id)
