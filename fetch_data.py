#!/usr/bin/env python3
################################################################################
# Name:    fetch_data.py
# Purpose: This Python 3 script fetches COVID-19 case data from the GitHub
#          repository and REST API of Johns Hopkins CSSE, DXY, KCDC, and
#          StatisticheCoronavirus, and creates GeoJSON and CSV files.
# Author:  Huidae Cho
# Since:   February 2, 2020
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

import requests
import io
import csv
import json
import datetime
import re
import os
import glob
import copy
import unicodedata
import traceback
import sys
import dic
import config

ts_confirmed_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv'
daily_url_format = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/{date}.csv'

features_url = 'https://services9.arcgis.com/N9p5hsImWXAccRNI/arcgis/rest/services/Nc2JKvYFoAEOFCG5JSI6/FeatureServer/1/query?where=1%3D1&outFields=*&f=json'

kcdc_country_url = 'http://ncov.mohw.go.kr/bdBoardList_Real.do'
kcdc_country_re = '누적 확진자 현황.*?\(([0-9]+)\.([0-9]+).*?([0-9]+)시.*?기준\).*?<td>([0-9,]+)</td>\s*<td>([0-9,]+)</td>\s*<td>[0-9,]+</td>\s*<td>([0-9,]+)</td>'
kcdc_provinces_url = 'http://ncov.mohw.go.kr/bdBoardList_Real.do?brdGubun=13'
kcdc_provinces_re = '([0-9]+)\.([0-9]+)\.\s*([0-9]+)시.*?기준.*?<tr class="sumline">.*?</tr>.*?(<tr>.+?)</tbody>'
kcdc_provinces_subre = '>([^>]+)</th>.*?<[^>]+?s_type1[^>]+>\s*([0-9,]+)\s*<.+?s_type4[^>]+>\s*([0-9,]+)\s*<.+?s_type2[^>]+>\s*([0-9,]+)\s*<'

dxy_url = 'https://ncov.dxy.cn/ncovh5/view/pneumonia'
dxy_re = 'window\.getListByCountryTypeService2true.*?"createTime":([0-9]+),.*window\.getAreaStat = (.*?)\}catch\(e\)'

statistichecoronavirus_url = 'https://statistichecoronavirus.it/coronavirus-italia/'
statistichecoronavirus_re = '<tr[^>]*>\s*<td[^>]*>(?:<[^>]*>){2}([^<>]*?)<[^>]*></td>\s*<td[^>]*>[^<>]*?</td>\s*<td[^>]*>([^<>]*?)</td>\s*<td[^>]*>[^<>]*?</td>\s*<td[^>]*>[^<>]*?</td>\s*<td[^>]*>([^<>]*?)</td>\s*<td[^>]*>([^<>]*?)</td>\s*</tr>'

minsal_url = 'https://www.minsal.cl/nuevo-coronavirus-2019-ncov/casos-confirmados-en-chile-covid-19/'
minsal_re = '<tr[^>]*>.*?<td[^>]*>([^<>]+)</td>.*?<td[^>]*>([0-9.]+)</td>.*?(?:<td[^>]*>[0-9.]+</td>.*?){3}<td[^>]*>([0-9.]+)</td>.*?<td[^>]*>[0-9,.]+ *%</td>.*?</tr>'
minsal_total_re = '<tr[^>]*>.*?<td[^>]*><strong>Total</strong></td>.*?<td[^>]*><strong>([0-9.]+)</strong></td>.*?(?:<td[^>]*><strong>[0-9.]+</strong></td>.*?){3}<td[^>]*><strong>([0-9.]+)</strong></td>.*?<td[^>]*><strong>[0-9,.]+ *%</strong></td>.*?</tr>.*?<tr[^>]*>.*?<td[^>]*><strong>Casos recuperados a nivel nacional\s*</strong></td>.*?<td[^>]*><strong>([0-9.]+)</strong></td>.*?</tr>'

geocode_country_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&key={config.bing_maps_key}'
geocode_province_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{province}}&key={config.bing_maps_key}'
geocode_admin2_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{admin2}},{{province}}&key={config.bing_maps_key}'

geodata_json = 'geodata.json'
data_csv = 'data.csv'

# use this dictionary to avoid geocoding the same province multiple times
coors_json = 'coors.json'

dates = []
data = []
key2data = {}
has_countries_to_display = True if len(config.countries_to_display) else False
has_duplicate_data = []
total_days = 0

def geocode(country, province='', admin2='', latitude=None, longitude=None):
    # https://docs.microsoft.com/en-us/bingmaps/rest-services/common-parameters-and-types/location-and-area-types
    # XXX: adminDistrict2 doesn't work?
    # adminDistrict=County,State works!

    # read existing data
    if os.path.exists(coors_json):
        with open(coors_json) as f:
            coors = json.load(f)
    else:
        coors = {}

    if admin2:
        location = f'{admin2}, {province}, {country}'
        geocode_url = geocode_admin2_url.format(country=country,
                province=province, admin2=admin2)
    elif province:
        location = f'{province}, {country}'
        geocode_url = geocode_province_url.format(country=country,
                province=province)
    else:
        location = country
        geocode_url = geocode_country_url.format(country=country)

    if location not in coors:
        if config.bing_maps_key == 'BING_MAPS_KEY':
            raise Exception('Please set up bing_maps_key in config.py')
        if config.bing_maps_referer == 'BING_MAPS_REFERER':
            raise Exception('Please set up bing_maps_referer in config.py')

        res = requests.get(geocode_url, headers={
            'referer': config.bing_maps_referer
        })
        ret = res.json()
        resources = ret['resourceSets'][0]['resources']
        if len(resources):
            coor = resources[0]['geocodePoints'][0]['coordinates']
            latitude = coor[0]
            longitude = coor[1]
        coors[location] = {'latitude': latitude, 'longitude': longitude}

        if latitude is not None and longitude is not None:
            with open(coors_json, 'w') as f:
                f.write(json.dumps(coors))
    else:
        latitude = coors[location]['latitude']
        longitude = coors[location]['longitude']

    return latitude, longitude

def fetch_csse_csv():
    global total_days

    print('Fetching CSSE CSV...')

    ts_confirmed_res = requests.get(ts_confirmed_url)
    with io.StringIO(ts_confirmed_res.content.decode()) as ts_confirmed_f:
        ts_confirmed_reader = csv.reader(ts_confirmed_f)
        header = ts_confirmed_reader.__next__()
        # reverse order to find more recent and fully populated data first
        j = 0
        for i in range(len(header) - 1, 3, -1):
            date = header[i].split('/')
            year = 2000 + int(date[2])
            month = int(date[0])
            day = int(date[1])

            date = f'{year}-{month:02}-{day:02}'
            dates.insert(0, date)

            print(f'{date}...', end='', flush=True)
            j += 1
            if j % 5 == 0:
                print('')

            fetch_csse_daily_csv(year, month, day)
            total_days += 1
        if j % 5:
            print('')

    for rec in data:
        for category in ('confirmed', 'recovered', 'deaths'):
            i = 0
            insert = {}
            for x in rec[category]:
                date = x['time'].strftime('%Y-%m-%d')
                while i < total_days - 1 and dates[i] < date:
                    insert[i] = {
                        'time': datetime.datetime.fromisoformat(
                            f'{dates[i]} 23:59:59+00:00'),
                        'count': 0,
                    }
                    i += 1
                i += 1
            for key in sorted(insert.keys()):
                rec[category].insert(key, insert[key])
            index = len(rec[category]) - 1
            while i < total_days:
                # TODO: aggregate
                rec[category].append({
                    'time': datetime.datetime.fromisoformat(
                        f'{dates[i]} 23:59:59+00:00'),
                    'count': rec[category][index]['count']
                })
                i += 1

    print('Fetching CSSE CSV completed')

def generate_key(country, province, admin2):
    if admin2:
        key = f'{admin2}, {province}, {country}'
    elif province:
        key = f'{province}, {country}'
    else:
        key = country
    return key

def read_key(key):
    x = key.split(', ')
    country = x.pop()
    province = x.pop() if len(x) else ''
    admin2 = x.pop() if len(x) else ''
    return country, province, admin2

def fetch_csse_daily_csv(year, month, day):
    date_iso = f'{year}-{month:02}-{day:02}'
    date_csv = f'{month:02}-{day:02}-{year}'

    url = daily_url_format.format(date=date_csv)
    res = requests.get(url)
    with io.StringIO(res.content.decode()) as f:
        reader = csv.reader(f)
        header = reader.__next__()
        ncols = len(header)
        for row in reader:
            admin2 = latitude = longitude = ''
            if ncols == 14 or ncols == 12:
                # since 03-22-2020
                # 0: FIPS
                # 1: Admin2
                # 2: Province_State
                # 3: Country_Region
                # 4: Last_Update
                # 5: Lat
                # 6: Long_
                # 7: Confirmed
                # 8: Deaths
                # 9: Recovered
                # 10: Active
                # 11: Combined_Key
                # since 05-29-2020
                # 12: Incidence_Rate
                # 13: Case-Fatality_Ratio
                admin2 = '' if row[1].strip() == 'None' else row[1].strip()
                province = '' if row[2].strip() == 'None' else row[2].strip()
                country = row[3].strip()
                # don't use last_updated; there can be duplicate entries with
                # different counts
                last_updated = row[4]
                if row[5] and row[5] != '0':
                    latitude = float(row[5])
                if row[6] and row[6] != '0':
                    longitude = float(row[6])
                c = int(0 if row[7] == '' else row[7])
                d = int(0 if row[8] == '' else row[8])
                r = int(0 if row[9] == '' else row[9])
            elif ncols == 8:
                # since 03-01-2020
                # 0: Province/State
                # 1: Country/Region
                # 2: Last Update
                # 3: Confirmed
                # 4: Deaths
                # 5: Recovered
                # 6: Latitude
                # 7: Longitude
                province = '' if row[0].strip() == 'None' else row[0].strip()
                country = row[1].strip()
                last_updated = row[2]
                c = int(0 if row[3] == '' else row[3])
                d = int(0 if row[4] == '' else row[4])
                r = int(0 if row[5] == '' else row[5])
                if row[6] and row[6] != '0':
                    latitude = float(row[6])
                if row[7] and row[7] != '0':
                    longitude = float(row[7])
            elif ncols == 6:
                # since 01-22-2020
                # 0: Province/State
                # 1: Country/Region
                # 2: Last Update
                # 3: Confirmed
                # 4: Deaths
                # 5: Recovered
                province = '' if row[0].strip() == 'None' else row[0].strip()
                country = row[1].strip()
                last_updated = row[2]
                c = int(0 if row[3] == '' else row[3])
                d = int(0 if row[4] == '' else row[4])
                r = int(0 if row[5] == '' else row[5])
            else:
                raise Exception('Unexpected format for daily report '
                        f'{date_csv}')
            if country in dic.co_names:
                country = dic.co_names[country]
            if ', ' in province and not admin2:
                admin2, province = province.split(', ')
            if ' County' in admin2:
                admin2 = admin2.replace(' County', '')
            elif ' Parish' in admin2:
                admin2 = admin2.replace(' Parish', '')
            if province in dic.us_states.keys():
                province = dic.us_states[province]
            if ',' in admin2:
                raise Exception('Commas are not allowed in admin2 names: '
                        f'{admin2} in {date_csv}')
            if ',' in province:
                raise Exception('Commas are not allowed in province names: '
                        f'{province} in {date_csv}')
            if ',' in country:
                raise Exception('Commas are not allowed in country names: '
                        f'{country} in {date_csv}')
            last_updated = datetime.datetime.fromisoformat(
                    f'{date_iso} 23:59:59+00:00')
            key = generate_key(country, province, admin2)
            if key in dic.keymap:
                key = dic.keymap[key]
                country, province, admin2 = read_key(key)
            if key in dic.latlong:
                latlong = dic.latlong[key]
                latitude = latlong['latitude']
                longitude = latlong['longitude']
            if not latitude or not longitude:
                latitude, longitude = geocode(country, province, admin2)
                if not latitude or not longitude:
                    raise Exception('Latitude or longitude is not defined for '
                            f'{key} in {date_csv}')
            if key not in key2data:
                if total_days > 0 and \
                   (country != 'United States' or
                    province not in dic.us_states.values() or
                    admin2 == 'Unassigned'):
                    continue
                # new record not in data
                index = len(data)
                key2data[key] = index
                # create and populate three lists with time series data
                confirmed = []
                recovered = []
                deaths = []
                data.append({
                    'country': country,
                    'province': province,
                    'admin2': admin2,
                    'latitude': latitude,
                    'longitude': longitude,
                    'confirmed': confirmed,
                    'recovered': recovered,
                    'deaths': deaths
                })
            else:
                # retrieve existing lists
                index = key2data[key]
                rec = data[index]
                confirmed = rec['confirmed']
                recovered = rec['recovered']
                deaths = rec['deaths']
                found = False
                for i in range(0, len(confirmed)):
                    if rec['confirmed'][i]['time'] == last_updated:
                        if c > rec['confirmed'][i]['count']:
                            rec['confirmed'][i]['count'] = c
                        if c > rec['recovered'][i]['count']:
                            rec['recovered'][i]['count'] = c
                        if c > rec['deaths'][i]['count']:
                            rec['deaths'][i]['count'] = c
                        found = True
                        break
                if found:
                    continue

            confirmed.insert(0, {
                'time': last_updated,
                'count': c
            })
            recovered.insert(0, {
                'time': last_updated,
                'count': r
            })
            deaths.insert(0, {
                'time': last_updated,
                'count': d
            })

def fetch_all_features(features_url):
    count = 1000
    offset = 0

    features = []
    while True:
        url = f'{features_url}&resultRecordCount={count}&resultOffset={offset}'
        if config.app_url == 'APP_URL':
            raise Exception('Please set up app_url in config.py')

        res = requests.get(url, headers={
            'referer': config.app_url
        })
        res = json.loads(res.content.decode())
        features.extend(res['features'])
        if 'exceededTransferLimit' not in res or \
           res['exceededTransferLimit'] == 'false':
            break
        offset += count
    return features

def fetch_csse_rest():
    global total_days

    print('Fetching CSSE REST...')

    features = fetch_all_features(features_url)
    with open('data/csse_rest.json', 'w') as f:
        f.write(json.dumps(features))

    today_iso = datetime.datetime.utcnow().strftime('%Y-%m-%d 00:00:00+00:00')
    today = datetime.datetime.fromisoformat(today_iso)

    # try to find most up-to-date info from the REST server
    for feature in features:
        attr = feature['attributes']
        c = int(attr['Confirmed'])
        r = int(attr['Recovered'])
        d = int(attr['Deaths'])

        if c + r + d == 0:
            continue

        country = attr['Country_Region'].strip()
        if country in dic.co_names:
            country = dic.co_names[country]
        province = attr['Province_State'].strip() \
            if attr['Province_State'] else ''
        admin2 = attr['Admin2'].strip() if attr['Admin2'] else ''
        last_updated = datetime.datetime.fromtimestamp(
                attr['Last_Update']/1000, tz=datetime.timezone.utc)
        # sometimes, the last date in the CSV file is later than REST; in this
        # case, let's use today's time at 00:00:00
        if today > last_updated:
            last_updated = today
        if 'geometry' in feature:
            latitude = feature['geometry']['y']
            longitude = feature['geometry']['x']

        key = generate_key(country, province, admin2)
        if key in dic.keymap:
            key = dic.keymap[key]
            country, province, admin2 = read_key(key)
        if key in dic.latlong:
            latlong = dic.latlong[key]
            latitude = latlong['latitude']
            longitude = latlong['longitude']
        if not latitude or not longitude:
            latitude, longitude = geocode(country, province, admin2)
            if not latitude or not longitude:
                raise Exception('Latitude or longitude is not defined for '
                        f'{key} in {date_csv}')
        if key not in key2data:
            # new record not in data
            index = len(data)
            key2data[key] = index
            # create and populate three lists with REST data
            confirmed = copy.deepcopy(data[0]['confirmed'])
            recovered = copy.deepcopy(data[0]['recovered'])
            deaths = copy.deepcopy(data[0]['deaths'])
            if len(confirmed) > total_days:
                index = len(confirmed) - 1
                del confirmed[index], recovered[index], deaths[index]
            for i in range(0, total_days):
                confirmed[i]['count'] = recovered[i]['count'] = \
                deaths[i]['count'] = 0
            data.append({
                'country': country,
                'province': province,
                'admin2': admin2,
                'latitude': latitude,
                'longitude': longitude,
                'confirmed': confirmed,
                'recovered': recovered,
                'deaths': deaths
            })

            if c:
                print(f'REST confirmed: {admin2}, {province}, {country}, '
                        f'0 => {c}')
            if r:
                print(f'REST recovered: {admin2}, {province}, {country}, '
                        f'0 => {r}')
            if d:
                print(f'REST deaths   : {admin2}, {province}, {country}, '
                        f'0 => {d}')
        else:
            # retrieve existing lists
            index = key2data[key]
            rec = data[index]
            country = rec['country']
            province = rec['province']
            admin2 = rec['admin2']
            confirmed = rec['confirmed']
            recovered = rec['recovered']
            deaths = rec['deaths']
            time = confirmed[len(confirmed) - 1]['time']
            # I found this case where a time from the spreadsheet is more
            # recent than the last updated time from the REST server
            if time > last_updated:
                last_updated = time

            index = len(confirmed) - 1
            c = max(confirmed[index]['count'], c)
            r = max(recovered[index]['count'], r)
            d = max(deaths[index]['count'], d)
            if c != confirmed[index]['count']:
                print(f'REST confirmed: {admin2}, {province}, {country}, '
                        f'{confirmed[index]["count"]} => {c}')
            if r != recovered[index]['count']:
                print(f'REST recovered: {admin2}, {province}, {country}, '
                        f'{recovered[index]["count"]} => {r}')
            if d != deaths[index]['count']:
                print(f'REST deaths   : {admin2}, {province}, {country}, '
                        f'{deaths[index]["count"]} => {d}')

        if len(confirmed) == total_days + 1:
            continue

        confirmed.append({
            'time': last_updated,
            'count': c
        }),
        recovered.append({
            'time': last_updated,
            'count': r
        }),
        deaths.append({
            'time': last_updated,
            'count': d
        })

    dates.append(today_iso.split()[0])
    total_days += 1

    # oops! some provinces are missing from the REST data?
    for rec in data:
        confirmed = rec['confirmed']
        recovered = rec['recovered']
        deaths = rec['deaths']
        index = len(confirmed) - 1
        if index == total_days - 1:
            continue
        confirmed.append(confirmed[index])
        recovered.append(recovered[index])
        deaths.append(deaths[index])

    print('Fetching CSSE REST completed')

def clean_us_data():
    country = 'United States'
    others_indices = []
    n = len(data)
    for i in range(0, n):
        rec = data[i]
        if rec['country'] != country:
            continue

        province = rec['province']
        admin2 = rec['admin2']
        if province not in dic.us_states.values():
            # non-CONUS records
            others_indices.append(i)
            if not admin2:
                rec['admin2'] = province
            continue
        elif admin2:
            # CONUS admin2 records
            continue

        # state-wide records
        confirmed = rec['confirmed']
        recovered = rec['recovered']
        deaths = rec['deaths']

        admin2_indices = []
        for j in range(0, n):
            rec2 = data[j]
            if rec2['country'] == country and \
               rec2['province'] == province and \
               rec2['admin2']:
                admin2_indices.append(j)
                if rec2['admin2'] == 'Unassigned':
                    rec2['latitude'] = rec['latitude']
                    rec2['longitude'] = rec['longitude']

        # no admin2 records
        if not len(admin2_indices):
            continue

        for j in range(0, len(confirmed)):
            c = r = d = 0
            for k in admin2_indices:
                rec2 = data[k]
                c += rec2['confirmed'][j]['count']
                r += rec2['recovered'][j]['count']
                d += rec2['deaths'][j]['count']
            if c > confirmed[j]['count']:
                print(f'US   confirmed: {province}, {country}, {dates[j]}, '
                        f'{confirmed[j]["count"]} => {c}')
                confirmed[j]['count'] = c
            if r > recovered[j]['count']:
                print(f'US   recovered: {province}, {country}, {dates[j]}, '
                        f'{recovered[j]["count"]} => {r}')
                recovered[j]['count'] = r
            if d > deaths[j]['count']:
                print(f'US   deaths   : {province}, {country}, {dates[j]}, '
                        f'{deaths[j]["count"]} => {d}')
                deaths[j]['count'] = d

    latitude, longitude = geocode(country)

    if len(others_indices):
        confirmed = []
        recovered = []
        deaths = []
        for i in range(0, total_days):
            c = r = d = 0
            last_updated = None
            for j in others_indices:
                rec = data[j]
                time = rec['confirmed'][i]['time']
                if last_updated is None or time > last_updated:
                    last_updated = time
                c += rec['confirmed'][i]['count']
                r += rec['recovered'][i]['count']
                d += rec['deaths'][i]['count']
            confirmed.append({
                'time': last_updated,
                'count': c
            })
            recovered.append({
                'time': last_updated,
                'count': r
            })
            deaths.append({
                'time': last_updated,
                'count': d
            })
        province = 'Others'

        print(f'US   confirmed: {province}, {country}, {c}')
        print(f'US   recovered: {province}, {country}, {r}')
        print(f'US   deaths   : {province}, {country}, {d}')

        data.append({
            'country': country,
            'province': province,
            'admin2': '',
            'latitude': latitude,
            'longitude': longitude,
            'confirmed': confirmed,
            'recovered': recovered,
            'deaths': deaths
        })

    confirmed = []
    recovered = []
    deaths = []
    for i in range(0, total_days):
        c = r = d = 0
        last_updated = None
        for rec in data:
            if rec['country'] == country and not rec['admin2']:
                time = rec['confirmed'][i]['time']
                if last_updated is None or time > last_updated:
                    last_updated = time
                c += rec['confirmed'][i]['count']
                r += rec['recovered'][i]['count']
                d += rec['deaths'][i]['count']
        confirmed.append({
            'time': last_updated,
            'count': c
        })
        recovered.append({
            'time': last_updated,
            'count': r
        })
        deaths.append({
            'time': last_updated,
            'count': d
        })

    print(f'US   confirmed: {country}, {c}')
    print(f'US   recovered: {country}, {r}')
    print(f'US   deaths   : {country}, {d}')

    data.append({
        'country': country,
        'province': '',
        'admin2': '',
        'latitude': latitude,
        'longitude': longitude,
        'confirmed': confirmed,
        'recovered': recovered,
        'deaths': deaths
    })

def get_data_filename(country, province=None):
    return 'data/' + (province + ', ' if province else '') + country + '.csv'

def fetch_kcdc_country():
    print('Fetching KCDC country...')

    res = requests.get(kcdc_country_url).content.decode()
    m = re.search(kcdc_country_re, res, re.DOTALL)
    if not m:
        raise Exception('Fetching KCDC country failed')

    print('Fetching KCDC country matched')

    year = 2020
    month = int(m[1])
    day = int(m[2])
    hour = int(m[3])
    confirmed = int(m[4].replace(',', ''))
    recovered = int(m[5].replace(',', ''))
    deaths = int(m[6].replace(',', ''))
    last_updated_iso = f'{year}-{month:02}-{day:02} {hour:02}:00:00+09:00'

    filename = get_data_filename('South Korea')
    add_header = True
    if os.path.exists(filename):
        add_header = False
        with open(filename) as f:
            reader = csv.reader(f)
            for row in reader:
                pass
            time = datetime.datetime.fromisoformat(row[0]).astimezone(
                    datetime.timezone.utc)
            if time >= datetime.datetime.fromisoformat(last_updated_iso).\
                    astimezone(datetime.timezone.utc):
                return

    with open(filename, 'a') as f:
        if add_header:
            f.write('time,confirmed,recovered,deaths\n')
        f.write(f'{last_updated_iso},{confirmed},{recovered},{deaths}\n')

    print('Fetching KCDC country completed')

def fetch_kcdc_provinces():
    print('Fetching KCDC provinces...')

    if not kcdc_provinces_re:
        print('Fetching KCDC provinces skipped')
        return

    res = requests.get(kcdc_provinces_url).content.decode()
    m = re.search(kcdc_provinces_re, res, re.DOTALL)
    if not m:
        raise Exception('Fetching KCDC provinces 1/2 failed')

    print('Fetching KCDC provinces 1/2 matched')

    country = 'South Korea'
    year = 2020
    month = int(m[1])
    day = int(m[2])
    hour = int(m[3])
    last_updated_iso = f'{year}-{month:02}-{day:02} {hour:02}:00:00+09:00'
    matches = re.findall(kcdc_provinces_subre, m[4])
    if not matches:
        raise Exception('Fetching KCDC provinces 2/2 failed')

    print('Fetching KCDC provinces 2/2 matched')

    last_updated = None
    for m in matches:
        province = dic.en[m[0]]
        confirmed = int(m[1].replace(',', ''))
        recovered = int(m[2].replace(',', ''))
        deaths = int(m[3].replace(',', ''))

        filename = get_data_filename(country, province)
        add_header = True
        if os.path.exists(filename):
            add_header = False
            with open(filename) as f:
                reader = csv.reader(f)
                for row in reader:
                    pass
                time = datetime.datetime.fromisoformat(row[0]).astimezone(
                        datetime.timezone.utc)
                if time >= datetime.datetime.fromisoformat(last_updated_iso).\
                        astimezone(datetime.timezone.utc):
                    continue

        with open(filename, 'a') as f:
            if add_header:
                f.write('time,confirmed,recovered,deaths\n')
            f.write(f'{last_updated_iso},{confirmed},{recovered},{deaths}\n')

    print('Fetching KCDC provinces completed')

def fetch_dxy():
    print('Fetching DXY...')

    res = requests.get(dxy_url).content.decode()
    m = re.search(dxy_re, res, re.DOTALL)
    if not m:
        raise Exception('Fetching DXY failed')

    print('Fetching DXY matched')

    last_updated = datetime.datetime.fromtimestamp(int(m[1])/1000,
            tz=datetime.timezone.utc)
    last_updated_iso = last_updated.strftime('%Y-%m-%d %H:%M:%S+00:00')
    for rec in json.loads(m[2]):
        province = rec['provinceShortName']
        if province not in dic.en:
            return
        province = dic.en[province]
        confirmed = rec['confirmedCount']
        recovered = rec['curedCount']
        deaths = rec['deadCount']

        country = 'China'
        if province == 'Taiwan':
            country = 'Taiwan'
            province = ''

        filename = get_data_filename(country, province)
        add_header = True
        if os.path.exists(filename):
            add_header = False
            with open(filename) as f:
                reader = csv.reader(f)
                for row in reader:
                    pass
                time = datetime.datetime.fromisoformat(row[0]).astimezone(
                        datetime.timezone.utc)
                if time >= last_updated:
                    continue

        with open(filename, 'a') as f:
            if add_header:
                f.write('time,confirmed,recovered,deaths\n')
            f.write(f'{last_updated_iso},{confirmed},{recovered},{deaths}\n')

    print('Fetching DXY completed')

def update_fetched_data(country, province, confirmed, recovered, deaths):
    now_iso = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S+00:00')
    today = now_iso.split()[0]

    filename = get_data_filename(country, province)
    add_header = True
    overwrite_row = 0
    if os.path.exists(filename):
        add_header = False
        with open(filename) as f:
            reader = csv.reader(f)
            for row in reader:
                overwrite_row += 1
            time_iso = row[0]
            time_date = time_iso.split()[0]
            if time_date != today:
                overwrite_row = 0

    if overwrite_row:
        with open(filename, 'r+') as f:
            for i in range(0, overwrite_row - 1):
                f.readline()
                seek = f.tell()
            f.seek(seek)
            f.write(f'{now_iso},{confirmed},{recovered},{deaths}\n')
    else:
        with open(filename, 'a') as f:
            if add_header:
                f.write('time,confirmed,recovered,deaths\n')
            f.write(f'{now_iso},{confirmed},{recovered},{deaths}\n')

def fetch_statistichecoronavirus():
    print('Fetching StatisticheCoronavirus...')

    res = requests.get(statistichecoronavirus_url).content.decode(
            errors='replace')
    matches = re.findall(statistichecoronavirus_re, res, re.DOTALL)
    if not matches:
        raise Exception('Fetching StatisticheCoronavirus failed')

    print('Fetching StatisticheCoronavirus matched')

    country = 'Italy'
    for m in matches:
        province = m[0]
        confirmed = int(m[1].replace('.', ''))
        recovered = int(m[3].replace('.', ''))
        deaths = int(m[2].replace('.', ''))
        update_fetched_data(country, province, confirmed, recovered, deaths)

    print('Fetching StatisticheCoronavirus completed')

# https://stackoverflow.com/a/518232
def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')

def fetch_minsal():
    print('Fetching Minsal...')

    res = requests.get(minsal_url).content.decode()
    matches = re.findall(minsal_re, res, re.DOTALL)
    if not matches:
        raise Exception('Fetching Minsal 1/2 failed')

    print('Fetching Minsal 1/2 matched')

    country = 'Chile'
    for m in matches:
        province = strip_accents(m[0].replace('&#8217;', ''))
        confirmed = int(m[1].replace('.', ''))
        recovered = 0
        deaths = int(m[2].replace('.', ''))
        update_fetched_data(country, province, confirmed, recovered, deaths)

    m = re.search(minsal_total_re, res, re.DOTALL)
    if not m:
        raise Exception('Fetching Minsal 2/2 failed')

    print('Fetching Minsal 2/2 matched')

    province = None
    confirmed = int(m[1].replace('.', ''))
    recovered = int(m[3].replace('.', ''))
    deaths = int(m[2].replace('.', ''))
    update_fetched_data(country, province, confirmed, recovered, deaths)

    print('Fetching Minsal completed')

def merge_local_data():
    global total_days

    for filename in glob.glob('data/*.csv'):
        key = filename.replace('data/', '').replace('.csv', '')
        if key.startswith('csse_'):
            continue
        country, province, admin2 = read_key(key)

        found = False
        for rec in data:
            if country == rec['country'] and \
               province == rec['province'] and \
               admin2 == rec['admin2']:
                found = True
                break

        if found:
            confirmed = rec['confirmed']
            recovered = rec['recovered']
            deaths = rec['deaths']
            index = len(confirmed) - 1
            time = confirmed[index]['time']

            with open(filename) as f:
                reader = csv.reader(f)
                for row in reader:
                    pass
                last_updated = datetime.datetime.fromisoformat(row[0]).\
                        astimezone(datetime.timezone.utc)
                if time > last_updated:
                    last_updated = time
                c = int(row[1])
                r = int(row[2])
                d = int(row[3])
                if c > confirmed[index]['count']:
                    print(f'data confirmed: {province}, {country}, '
                            f'{confirmed[index]["count"]} => {c}')
                    confirmed[index] = {
                        'time': last_updated,
                        'count': c
                    }
                if r > recovered[index]['count']:
                    print(f'data recovered: {province}, {country}, '
                            f'{recovered[index]["count"]} => {r}')
                    recovered[index] = {
                        'time': last_updated,
                        'count': r
                    }
                if d > deaths[index]['count']:
                    print(f'data deaths   : {province}, {country}, '
                            f'{deaths[index]["count"]} => {d}')
                    deaths[index] = {
                        'time': last_updated,
                        'count': d
                    }
        else:
            if province and country not in has_duplicate_data:
                has_duplicate_data.append(country)

            latitude, longitude = geocode(country, province, admin2)

            confirmed = []
            recovered = []
            deaths = []

            with open(filename) as f:
                reader = csv.reader(f)
                reader.__next__()
                for row in reader:
                    time = datetime.datetime.fromisoformat(row[0]).\
                            astimezone(datetime.timezone.utc)
                    if config.use_local_data_only:
                        date = time.strftime('%Y-%m-%d')
                        if date not in dates:
                            dates.append(date)

                    c = int(row[1])
                    r = int(row[2])
                    d = int(row[3])
                    confirmed.append({
                        'time': time,
                        'count': c
                    })
                    recovered.append({
                        'time': time,
                        'count': r
                    })
                    deaths.append({
                        'time': time,
                        'count': d
                    })

            print(f'data confirmed: {admin2}, {province}, {country}, {c}')
            print(f'data recovered: {admin2}, {province}, {country}, {r}')
            print(f'data deaths   : {admin2}, {province}, {country}, {d}')

            data.append({
                'country': country,
                'province': province,
                'admin2': admin2,
                'latitude': latitude,
                'longitude': longitude,
                'confirmed': confirmed,
                'recovered': recovered,
                'deaths': deaths
            })

    if config.use_local_data_only:
        dates.sort()
        total_days = len(dates)

    for country in has_duplicate_data:
        total_confirmed = total_recovered = total_deaths = 0
        co_confirmed = co_recovered = co_deaths = 0
        co_rec = None
        last_updated = None
        for rec in data:
            co = rec['country']
            if co != country:
                continue
            province = rec['province']
            confirmed = rec['confirmed']
            recovered = rec['recovered']
            deaths = rec['deaths']
            index = len(confirmed) - 1
            time = confirmed[index]['time']
            c = confirmed[index]['count']
            r = recovered[index]['count']
            d = deaths[index]['count']
            if province:
                if not last_updated or time > last_updated:
                    last_updated = time
                total_confirmed += c
                total_recovered += r
                total_deaths += d
            else:
                co_rec = rec
                co_last_updated = time
                co_confirmed = c
                co_recovered = r
                co_deaths = d

        if co_confirmed == total_confirmed and \
           co_recovered == total_recovered and \
           co_deaths == total_deaths:
            # remote data is exactly the same as local data
            continue

        index = len(co_rec['confirmed']) - 1
        c = r = d = 0
        if last_updated > co_last_updated:
            # local data is newer
            co_rec['confirmed'][index]['time'] = \
            co_rec['recovered'][index]['time'] = \
            co_rec['deaths'][index]['time'] = last_updated
        else:
            # remote data is newer
            last_updated = co_last_updated

        # be conservative!
        if co_confirmed > total_confirmed:
            c = co_confirmed - total_confirmed
        elif total_confirmed > co_confirmed:
            print(f'data confirmed: {country}, {co_confirmed} => '
                    f'{total_confirmed}')
            co_rec['confirmed'][index]['count'] = total_confirmed
        if co_recovered > total_recovered:
            r = co_recovered - total_recovered
        elif total_recovered > co_recovered:
            print(f'data recovered: {country}, {co_recovered} => '
                    f'{total_recovered}')
            co_rec['recovered'][index]['count'] = total_recovered
        if co_deaths > total_deaths:
            d = co_deaths - total_deaths
        elif total_deaths > co_deaths:
            print(f'data deaths   : {country}, {co_deaths} => {total_deaths}')
            co_rec['deaths'][index]['count'] = total_deaths

        if c + r + d == 0:
            continue

        province = 'Others'
        latitude = co_rec['latitude']
        longitude = co_rec['longitude']

        print(f'data confirmed: {province}, {country}, {c}')
        print(f'data recovered: {province}, {country}, {r}')
        print(f'data deaths   : {province}, {country}, {d}')

        confirmed = [{
            'time': last_updated,
            'count': c
        }]
        recovered = [{
            'time': last_updated,
            'count': r
        }]
        deaths = [{
            'time': last_updated,
            'count': d
        }]
        data.append({
            'country': country,
            'province': province,
            'admin2': admin2,
            'latitude': latitude,
            'longitude': longitude,
            'confirmed': confirmed,
            'recovered': recovered,
            'deaths': deaths
        })

def sort_data():
    # sort records by confirmed, country, and province
    data.sort(key=lambda x: (
        -x['confirmed'][len(x['confirmed'])-1]['count'],
        x['country'],
        x['province']))

def report_data():
    total_confirmed = total_recovered = total_deaths = 0
    for rec in data:
        country = rec['country']
        province = rec['province']
        admin2 = rec['admin2']
        latitude = rec['latitude']
        longitude = rec['longitude']
        index = len(rec['confirmed']) - 1
        c = rec['confirmed'][index]['count']
        r = rec['recovered'][index]['count']
        d = rec['deaths'][index]['count']
        if c + r + d == 0 or \
           (country in has_duplicate_data and not province) or \
           (country == 'United States' and not admin2):
            continue
        print(f'final: {admin2}, {province}, {country}, '
                f'{latitude}, {longitude}, {c}, {r}, {d}')
        total_confirmed += c
        total_recovered += r
        total_deaths += d

    print(f'Total confirmed: {total_confirmed}')
    print(f'Total recovered: {total_recovered}')
    print(f'Total deaths   : {total_deaths}')

def write_geojson():
    # create a new list to store all the features
    features = []
    # create a feature collection
    feature_id = 0
    for rec in data:
        country = rec['country']
        province = rec['province']
        admin2 = rec['admin2']
        index = len(rec['confirmed']) - 1
        if (rec['confirmed'][index]['count'] +
            rec['recovered'][index]['count'] +
            rec['deaths'][index]['count'] == 0) or \
           (has_countries_to_display and
            country not in config.countries_to_display):
            continue
        features.append({
            'id': feature_id,
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [
                    round(rec['longitude'], 4),
                    round(rec['latitude'], 4)
                ]
            },
            'properties': {
                'country': country,
                'province': province,
                'admin2': admin2,
                'confirmed': rec['confirmed'],
                'recovered': rec['recovered'],
                'deaths': rec['deaths']
            }
        })
        feature_id += 1

    # finally, build the output GeoJSON object and save it
    geodata = {
        'type': 'FeatureCollection',
        'features': features
    }

    def convert_time(x):
        if isinstance(x, datetime.datetime):
            return int(x.timestamp())

    with open(geodata_json, 'w') as f:
        f.write(json.dumps(geodata, default=convert_time))

def write_csv():
    with open(data_csv, 'w') as f:
        f.write('admin2,province,country,latitude,longitude,category')
        for date in dates:
            date = date.replace('-', '')
            f.write(f',utc_{date}')
        f.write('\n')
        for rec in data:
            country = rec['country']
            province = rec['province']
            admin2 = rec['admin2']
            index = len(rec['confirmed']) - 1
            if (rec['confirmed'][index]['count'] +
                rec['recovered'][index]['count'] +
                rec['deaths'][index]['count'] == 0) or \
               (has_countries_to_display and
                country not in config.countries_to_display):
                continue
            if ',' in admin2:
                admin2 = f'"{admin2}"'
            if ',' in province:
                province = f'"{province}"'
            if ',' in country:
                country = f'"{country}"'
            latitude = round(rec['latitude'], 4)
            longitude = round(rec['longitude'], 4)
            for category in ('confirmed', 'recovered', 'deaths'):
                f.write(f'{admin2},{province},{country},{latitude},{longitude},'
                        f'{category}')
                i = 0
                count = 0
                for x in rec[category]:
                    date = x['time'].strftime('%Y-%m-%d')
                    while i < total_days - 1 and dates[i] < date:
                        f.write(f',{count}')
                        i += 1
                    i += 1
                    count = x['count']
                    f.write(f',{count}')
                while i < total_days:
                    f.write(f',{count}')
                    i += 1
                f.write('\n')

if __name__ == '__main__':
    if not config.use_local_data_only:
        fetch_csse_csv()
        fetch_csse_rest()
        clean_us_data()
#        try:
#            fetch_kcdc_country()
#        except:
#            traceback.print_exc(file=sys.stdout)
#        try:
#            fetch_kcdc_provinces()
#        except:
#            traceback.print_exc(file=sys.stdout)
#        try:
#            fetch_dxy()
#        except:
#            traceback.print_exc(file=sys.stdout)
#        try:
#            fetch_statistichecoronavirus()
#        except:
#            traceback.print_exc(file=sys.stdout)
#        try:
#            fetch_minsal()
#        except:
#            traceback.print_exc(file=sys.stdout)
#    try:
#        merge_local_data()
#    except:
#        traceback.print_exc(file=sys.stdout)
    sort_data()
    report_data()
    write_geojson()
    write_csv()
