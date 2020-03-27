#!/usr/bin/env python3
################################################################################
# Name:    check_rest_data.py
# Purpose: This Python 3 script counts cases from the REST data for a specified
#          country or all countries.
# Author:  Huidae Cho
# Since:   March 27, 2020
#
# Copyright (C) 2020, Huidae Cho <https://idea.isnew.info>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
################################################################################

import sys
import json

with open('data/csse_rest.json') as f:
    features = json.load(f)

country = sys.argv[1] if len(sys.argv) >= 2 else ''

confirmed = recovered = deaths = 0
for feature in features:
    attr = feature['attributes']
    co = attr['Country_Region']
    province = attr['Province_State']
    admin2 = attr['Admin2']
    c = attr['Confirmed']
    r = attr['Recovered']
    d = attr['Deaths']
    if not country or co == country:
        print(f'{admin2},{province},{co},{c},{r},{d}')
        confirmed += c
        recovered += r
        deaths += d

print(f'Total,Total,{country if country else "Global"},{confirmed},{recovered},{deaths}')
