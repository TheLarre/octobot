#  Drakkar-Software OctoBot-Interfaces
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
import flask
import os
import tentacles.Services.Interfaces.web_interface.models as models


def send_and_remove_file(file_path, download_name):
    try:
        return flask.send_file(file_path, as_attachment=True, download_name=download_name, max_age=0)
    finally:
        # cleanup temp_file
        def remove_file(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        models.schedule_delayed_command(remove_file, file_path, delay=2)
