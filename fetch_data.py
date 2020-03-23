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
import dic
import config

features_url = 'https://services1.arcgis.com/0MSEUqKaxRlEPj5g/ArcGIS/rest/services/ncov_cases/FeatureServer/1/query?where=1%3D1&outFields=*&f=json'

confirmed_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv'
recovered_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Recovered.csv'
deaths_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Deaths.csv'

kcdc_country_url = 'http://ncov.mohw.go.kr/bdBoardList_Real.do'
kcdc_country_re = '발생현황\s*\(([0-9]+)\.([0-9]+).*?([0-9]+)시.*?기준\).*?>누적 확진자 현황<.*?tbody>\s*<tr>\s*<td>([0-9,]+)</td>\s*<td>([0-9,]+)</td>\s*<td>[0-9,]+</td>\s*<td>([0-9,]+)</td>'
kcdc_provinces_url = 'http://ncov.mohw.go.kr/bdBoardList_Real.do?brdGubun=13'
kcdc_provinces_re = '([0-9]+)\.([0-9]+)\.\s*([0-9]+)시.*?기준.*?<tr class="sumline">.*?</tr>.*?(<tr>.+?)</tbody>'
kcdc_provinces_subre = '>([^>]+)</th>.*?<[^>]+?s_type1[^>]+>\s*([0-9,]+)\s*<.+?s_type4[^>]+>\s*([0-9,]+)\s*<.+?s_type2[^>]+>\s*([0-9,]+)\s*<'

dxy_url = 'https://ncov.dxy.cn/ncovh5/view/pneumonia'
dxy_re = 'window\.getListByCountryTypeService2true.*?"createTime":([0-9]+),.*window\.getAreaStat = (.*?)\}catch\(e\)'

statistichecoronavirus_url = 'https://statistichecoronavirus.it/regioni-coronavirus-italia/'
statistichecoronavirus_re = '<tr[^>]*>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>.*?</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>.*?</td>.*?<td[^>]*>.*?</td>.*?<td[^>]*>(.*?)</td>.*?<td[^>]*>(.*?)</td>'

geocode_province_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{province}}&key={config.bing_maps_key}'
geocode_country_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&key={config.bing_maps_key}'

geodata_json = 'geodata.json'
data_csv = 'data.csv'

# use this dictionary to avoid geocoding the same province multiple times
coors_json = 'coors.json'

data = []
key2data = {}
has_countries_to_display = True if len(config.countries_to_display) else False
has_duplicate_data = []
use_us_county_level = False

def geocode(country, province, latitude=None, longitude=None):
    # read existing data
    if os.path.exists(coors_json):
        with open(coors_json) as f:
            coors = json.load(f)
    else:
        coors = {}

    if province == '':
        location = country
        geocode_url = geocode_country_url.format(country=country)
    else:
        location = f'{province}, {country}'
        geocode_url = geocode_province_url.format(country=country,
                province=province)
    if location not in coors:
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

    confirmed_res = requests.get(confirmed_url)
    recovered_res = requests.get(recovered_url)
    deaths_res = requests.get(deaths_url)

    with open('data/csse_confirmed.csv', 'w') as f:
        f.write(confirmed_res.content.decode())
    with open('data/csse_recovered.csv', 'w') as f:
        f.write(recovered_res.content.decode())
    with open('data/csse_deaths.csv', 'w') as f:
        f.write(deaths_res.content.decode())

    with io.StringIO(confirmed_res.content.decode()) as confirmed_f,\
         io.StringIO(recovered_res.content.decode()) as recovered_f,\
         io.StringIO(deaths_res.content.decode()) as deaths_f:
        confirmed_reader = csv.reader(confirmed_f)
        recovered_reader = csv.reader(recovered_f)
        deaths_reader = csv.reader(deaths_f)

        # assume these header rows are all identical
        confirmed_header = confirmed_reader.__next__()
        recovered_header = recovered_reader.__next__()
        deaths_header = deaths_reader.__next__()
        num_cols = len(confirmed_header)
        total_days = num_cols - 4

        # for each province
        for confirmed_row in confirmed_reader:
            recovered_row = recovered_reader.__next__()
            deaths_row = deaths_reader.__next__()

            if len(confirmed_row) < num_cols:
                continue

            col = 0
            province = confirmed_row[col]; col += 1
            province = '' if province == 'None' else province.strip()
            country = confirmed_row[col].strip(); col += 1
            if country in dic.co_names:
                country = dic.co_names[country]

            # retrieve coordinates from the geocoding server if desired;
            # otherwise, just use coordinates from the spreadsheet
            latitude = float(confirmed_row[col]); col += 1
            longitude = float(confirmed_row[col]); col += 1
            if config.geocode:
                latitude, longitude = geocode(country, province,
                        latitude, longitude)

            key = f'{province}, {country}'
            if key in dic.latlong:
                latlong = dic.latlong[key]
                latitude = latlong['latitude']
                longitude = latlong['longitude']
            latitude = round(latitude, 4)
            longitude = round(longitude, 4)

            if key in dic.keymap:
                key = dic.keymap[key]
                (province, country) = key.split(', ')
            if key not in key2data:
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
                    'latitude': latitude,
                    'longitude': longitude,
                    'confirmed': confirmed,
                    'recovered': recovered,
                    'deaths': deaths
                })
                append = True
            else:
                # retrieve existing lists
                index = key2data[key]
                rec = data[index]
                confirmed = rec['confirmed']
                recovered = rec['recovered']
                deaths = rec['deaths']
                append = False

            for j in range(col, len(confirmed_row)):
                date = confirmed_header[j].split('/')
                time = datetime.datetime(2000 + int(date[2]), int(date[0]),
                        int(date[1]), 23, 59, tzinfo=datetime.timezone.utc)
                # YYYY/MM/DD UTC for iOS
                time_str = f'{time.strftime("%Y/%m/%d %H:%M:%S UTC")}'

                c = int(confirmed_row[j]) if confirmed_row[j] else 0
                r = int(recovered_row[j]) if recovered_row[j] else 0
                d = int(deaths_row[j]) if deaths_row[j] else 0

                if append:
                    confirmed.append({
                        'time': time_str,
                        'count': c
                    })
                    recovered.append({
                        'time': time_str,
                        'count': r
                    })
                    deaths.append({
                        'time': time_str,
                        'count': d
                    })
                else:
                    confirmed[j - col]['count'] = max(confirmed[j - col]['count'], c)
                    recovered[j - col]['count'] = max(recovered[j - col]['count'], r)
                    deaths[j - col]['count'] = max(deaths[j - col]['count'], d)

    print('Fetching CSSE CSV completed')

def fetch_csse_rest():
    global total_days

    print('Fetching CSSE REST...')

    res = requests.get(features_url)

    with open('data/csse_rest.json', 'w') as f:
        f.write(res.content.decode())

    features = json.loads(res.content)['features']

    # try to find most up-to-date info from the REST server
    for feature in features:
        attr = feature['attributes']
        c = int(attr['Confirmed'])
        r = int(attr['Recovered'])
        d = int(attr['Deaths'])

        if c == 0:
            continue

        country = attr['Country_Region'].strip()
        if country in dic.co_names:
            country = dic.co_names[country]
        province = attr['Province_State'].strip() if attr['Province_State'] else ''
        last_updated = datetime.datetime.fromtimestamp(
                attr['Last_Update']/1000, tz=datetime.timezone.utc)
        last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
        latitude = feature['geometry']['y']
        longitude = feature['geometry']['x']

        key = f'{province}, {country}'
        if key in dic.latlong:
            latlong = dic.latlong[key]
            latitude = latlong['latitude']
            longitude = latlong['longitude']
        latitude = round(latitude, 4)
        longitude = round(longitude, 4)

        if key in dic.keymap:
            key = dic.keymap[key]
            (province, country) = key.split(', ')
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
                confirmed[i]['count'] = recovered[i]['count'] = deaths[i]['count'] = 0
            data.append({
                'country': country,
                'province': province,
                'latitude': latitude,
                'longitude': longitude,
                'confirmed': confirmed,
                'recovered': recovered,
                'deaths': deaths
            })
            existing = False
        else:
            # retrieve existing lists
            index = key2data[key]
            rec = data[index]
            country = rec['country']
            province = rec['province']
            confirmed = rec['confirmed']
            recovered = rec['recovered']
            deaths = rec['deaths']
            time_str = confirmed[len(confirmed) - 1]['time']
            # I found this case where a time from the spreadsheet is more
            # recent than the last updated time from the REST server
            if time_str > last_updated_str:
                last_updated_str = time_str
            existing = True

        if existing:
            index = len(confirmed) - 1
            c = max(confirmed[index]['count'], c)
            r = max(recovered[index]['count'], r)
            d = max(deaths[index]['count'], d)
            if c != confirmed[index]['count']:
                print(f'REST confirmed: {province}, {country}, {confirmed[index]["count"]} => {c}')
            if r != recovered[index]['count']:
                print(f'REST recovered: {province}, {country}, {recovered[index]["count"]} => {r}')
            if d != deaths[index]['count']:
                print(f'REST deaths   : {province}, {country}, {deaths[index]["count"]} => {d}')
        else:
            if c:
                print(f'REST confirmed: {province}, {country}, 0 => {c}')
            if r:
                print(f'REST recovered: {province}, {country}, 0 => {r}')
            if d:
                print(f'REST deaths   : {province}, {country}, 0 => {d}')

        if len(confirmed) == total_days + 1:
            continue

        confirmed.append({
            'time': last_updated_str,
            'count': c
        }),
        recovered.append({
            'time': last_updated_str,
            'count': r
        }),
        deaths.append({
            'time': last_updated_str,
            'count': d
        })

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
    if use_us_county_level:
        return

    sts = list(dic.us_states.keys())
    states = list(dic.us_states.values())
    n = len(data)

    for rec in data:
        if rec['country'] != 'United States':
            continue

        province = rec['province']
        if province not in states:
            continue

        st = sts[states.index(province)]
        confirmed = rec['confirmed']
        recovered = rec['recovered']
        deaths = rec['deaths']

        st_indices = []
        for i in range(0, n):
            rec2 = data[i]
            if rec2['country'] == 'United States' and rec2['province'].endswith(f', {st}'):
                st_indices.append(i)

        for i in range(0, len(confirmed)):
            if confirmed[i]['count'] > 0:
                break
            for j in st_indices:
                confirmed[i]['count'] += data[j]['confirmed'][i]['count']

def get_data_filename(country, province=None):
    return 'data/' + (province + ', ' if province else '') + country + '.csv'

def fetch_kcdc_country():
    print('Fetching KCDC country...')

    res = requests.get(kcdc_country_url).content.decode()
    m = re.search(kcdc_country_re, res, re.DOTALL)
    if not m:
        print('Fetching KCDC country failed')
        return

    print('Fetching KCDC country matched')

    year = 2020
    month = int(m[1])
    date = int(m[2])
    hour = int(m[3])
    confirmed = int(m[4].replace(',', ''))
    recovered = int(m[5].replace(',', ''))
    deaths = int(m[6].replace(',', ''))
    last_updated_iso = f'{year}-{month:02}-{date:02} {hour:02}:00:00+09:00'

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
        print('Fetching KCDC provinces 1/2 failed')
        return

    print('Fetching KCDC provinces 1/2 matched')

    country = 'South Korea'
    year = 2020
    month = int(m[1])
    date = int(m[2])
    hour = int(m[3])
    last_updated_iso = f'{year}-{month:02}-{date:02} {hour:02}:00:00+09:00'
    matches = re.findall(kcdc_provinces_subre, m[4])
    if not matches:
        print('Fetching KCDC provinces 2/2 failed')

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
        print('Fetching DXY failed')
        return

    print('Fetching DXY matched')

    last_updated = datetime.datetime.fromtimestamp(int(m[1])/1000,
            tz=datetime.timezone.utc)
    last_updated_iso = f'{last_updated.strftime("%Y-%m-%d %H:%M:%S+00:00")}'
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

def fetch_statistichecoronavirus():
    print('Fetching StatisticheCoronavirus...')

    res = requests.get(statistichecoronavirus_url).content.decode()
    matches = re.findall(statistichecoronavirus_re, res, re.DOTALL)
    if not matches:
        print('Fetching StatisticheCoronavirus failed')
        return

    print('Fetching StatisticheCoronavirus matched')

    country = 'Italy'
    now_iso = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S+00:00')
    for m in matches:
        province = m[0]
        confirmed = int(m[1].replace('.', ''))
        recovered = int(m[3].replace('.', ''))
        deaths = int(m[2].replace('.', ''))

        filename = get_data_filename(country, province)
        add_header = True
        if os.path.exists(filename):
            add_header = False
            with open(filename) as f:
                reader = csv.reader(f)
                for row in reader:
                    pass
                c = int(row[1])
                r = int(row[2])
                d = int(row[3])
                if confirmed == c and recovered == r and deaths == d:
                    continue

        with open(filename, 'a') as f:
            if add_header:
                f.write('time,confirmed,recovered,deaths\n')
            f.write(f'{now_iso},{confirmed},{recovered},{deaths}\n')

    print('Fetching StatisticheCoronavirus completed')

def merge_data():
    for filename in glob.glob('data/*.csv'):
        name = filename.replace('data/', '').replace('.csv', '')
        if name.startswith('csse_'):
            continue
        if ',' in name:
            x = name.split(',')
            province = x[0].strip()
            country = x[1].strip()
        else:
            province = ''
            country = name

        found = False
        for rec in data:
            if country == rec['country'] and province == rec['province']:
                found = True
                break

        if found:
            confirmed = rec['confirmed']
            recovered = rec['recovered']
            deaths = rec['deaths']
            index = len(confirmed) - 1
            time_str = confirmed[index]['time']

            with open(filename) as f:
                reader = csv.reader(f)
                for row in reader:
                    pass
                last_updated = datetime.datetime.fromisoformat(row[0]).\
                        astimezone(datetime.timezone.utc)
                last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
                if time_str > last_updated_str:
                    last_updated_str = time_str
                c = int(row[1])
                r = int(row[2])
                d = int(row[3])
                if c > confirmed[index]['count']:
                    print(f'data confirmed: {province}, {country}, {confirmed[index]["count"]} => {c}')
                    confirmed[index] = {
                        'time': last_updated_str,
                        'count': c
                    }
                if r > recovered[index]['count']:
                    print(f'data recovered: {province}, {country}, {recovered[index]["count"]} => {r}')
                    recovered[index] = {
                        'time': last_updated_str,
                        'count': r
                    }
                if d > deaths[index]['count']:
                    print(f'data deaths   : {province}, {country}, {deaths[index]["count"]} => {d}')
                    deaths[index] = {
                        'time': last_updated_str,
                        'count': d
                    }
        else:
            if province and country not in has_duplicate_data:
                has_duplicate_data.append(country)

            latitude, longitude = geocode(country, province)
            latitude = round(latitude, 4)
            longitude = round(longitude, 4)

            confirmed = []
            recovered = []
            deaths = []

            with open(filename) as f:
                reader = csv.reader(f)
                reader.__next__()
                for row in reader:
                    time = datetime.datetime.fromisoformat(row[0]).\
                            astimezone(datetime.timezone.utc)
                    time_str = f'{time.strftime("%Y/%m/%d %H:%M:%S UTC")}'
                    c = int(row[1])
                    r = int(row[2])
                    d = int(row[3])
                    confirmed.append({
                        'time': time_str,
                        'count': c
                    })
                    recovered.append({
                        'time': time_str,
                        'count': r
                    })
                    deaths.append({
                        'time': time_str,
                        'count': d
                    })

                print(f'data confirmed: {province}, {country}, {c}')
                print(f'data recovered: {province}, {country}, {r}')
                print(f'data deaths   : {province}, {country}, {d}')

            data.append({
                'country': country,
                'province': province,
                'latitude': latitude,
                'longitude': longitude,
                'confirmed': confirmed,
                'recovered': recovered,
                'deaths': deaths
            })

    for country in has_duplicate_data:
        total_confirmed = total_recovered = total_deaths = 0
        co_confirmed = co_recovered = co_deaths = 0
        co_rec = None
        last_updated_str = None
        for rec in data:
            co = rec['country']
            if co != country:
                continue
            province = rec['province']
            confirmed = rec['confirmed']
            recovered = rec['recovered']
            deaths = rec['deaths']
            index = len(confirmed) - 1
            time_str = confirmed[index]['time']
            c = confirmed[index]['count']
            r = recovered[index]['count']
            d = deaths[index]['count']
            if province:
                if not last_updated_str or time_str > last_updated_str:
                    last_updated_str = time_str
                total_confirmed += c
                total_recovered += r
                total_deaths += d
            else:
                co_rec = rec
                co_last_updated_str = time_str
                co_confirmed = c
                co_recovered = r
                co_deaths = d

        if co_confirmed == total_confirmed and \
           co_recovered == total_recovered and \
           co_deaths == total_deaths:
            # remote data is exactly the same as local data
            continue

        index = len(co_rec['confirmed']) - 1
        add_others = False
        c = r = d = 0
        if last_updated_str > co_last_updated_str:
            # local data is newer
            co_rec['confirmed'][index]['time'] = \
            co_rec['recovered'][index]['time'] = \
            co_rec['deaths'][index]['time'] = last_updated_str
        else:
            # remote data is newer
            last_updated_str = co_last_updated_str

        # be conservative!
        if co_confirmed > total_confirmed:
            c = co_confirmed - total_confirmed
        elif total_confirmed > co_confirmed:
            print(f'data confirmed: {country}, {co_confirmed} => {total_confirmed}')
            co_rec['confirmed'][index]['count'] = total_confirmed
        if co_recovered > total_recovered:
            r = co_recovered - total_recovered
        elif total_recovered > co_recovered:
            print(f'data recovered: {country}, {co_recovered} => {total_recovered}')
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
            'time': last_updated_str,
            'count': c
        }]
        recovered = [{
            'time': last_updated_str,
            'count': r
        }]
        deaths = [{
            'time': last_updated_str,
            'count': d
        }]
        data.append({
            'country': country,
            'province': province,
            'latitude': latitude,
            'longitude': longitude,
            'confirmed': confirmed,
            'recovered': recovered,
            'deaths': deaths
        })

def sort_data():
    global data

    # sort records by confirmed, country, and province
    data = sorted(data, key=lambda x: (
        -x['confirmed'][len(x['confirmed'])-1]['count'],
        x['country'],
        x['province']))

def report_data():
    total_confirmed = total_recovered = total_deaths = 0
    for rec in data:
        country = rec['country']
        province = rec['province']
        latitude = rec['latitude']
        longitude = rec['longitude']
        index = len(rec['confirmed']) - 1
        c = rec['confirmed'][index]['count']
        r = rec['recovered'][index]['count']
        d = rec['deaths'][index]['count']
        if c == 0 or (country in has_duplicate_data and not province):
            continue
        if country == 'United States' and \
           ((use_us_county_level and province in dic.us_states.values()) or
            (not use_us_county_level and province[-2:] in dic.us_states)):
            continue
        print(f'final: {province}; {country}; {latitude}; {longitude}; {c}; {r}; {d}')
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
    for i in range(0, len(data)):
        rec = data[i]
        country = rec['country']
        province = rec['province']
        index = len(rec['confirmed']) - 1
        if rec['confirmed'][index]['count'] == 0 and \
           rec['recovered'][index]['count'] == 0 and \
           rec['deaths'][index]['count'] == 0:
            continue
        if country == 'United States':
            if (use_us_county_level and province in dic.us_states.values()) or \
               (not use_us_county_level and province[-2:] in dic.us_states):
                continue
        if has_countries_to_display and \
           country not in config.countries_to_display:
            continue
        features.append({
            'id': i,
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [rec['longitude'], rec['latitude']]
            },
            'properties': {
                'country': rec['country'],
                'province': rec['province'],
                'confirmed': rec['confirmed'],
                'recovered': rec['recovered'],
                'deaths': rec['deaths']
            }
        })

    # finally, build the output GeoJSON object and save it
    geodata = {
        'type': 'FeatureCollection',
        'features': features
    }

    with open(geodata_json, 'w') as f:
        f.write(json.dumps(geodata))

def write_csv():
    with open(data_csv, 'w') as f:
        f.write('province,country,latitude,longitude,category')
        for x in data[0]['confirmed']:
            date = x['time'].split(' ')[0].replace('/', '')
            f.write(f',utc_{date}')
        f.write('\n')
        for rec in data:
            country = rec['country']
            province = rec['province']
            index = len(rec['confirmed']) - 1
            if rec['confirmed'][index]['count'] == 0 and \
               rec['recovered'][index]['count'] == 0 and \
               rec['deaths'][index]['count'] == 0:
                continue
            if country == 'United States':
                if (use_us_county_level and province in dic.us_states.values()) or \
                   (not use_us_county_level and province[-2:] in dic.us_states):
                    continue
            if has_countries_to_display and \
               country not in config.countries_to_display:
                continue
            if ',' in province:
                province = f'"{province}"'
            if ',' in country:
                country = f'"{country}"'
            latitude = rec['latitude']
            longitude = rec['longitude']
            for category in ('confirmed', 'recovered', 'deaths'):
                f.write(f'{province},{country},{latitude},{longitude},{category}')
                for i in range(len(rec[category]), total_days):
                    f.write(',0')
                for x in rec[category]:
                    f.write(f',{x["count"]}')
                f.write('\n')

if __name__ == '__main__':
    fetch_csse_csv()
    fetch_csse_rest()
    clean_us_data()

    fetch_kcdc_country()
    fetch_kcdc_provinces()
    fetch_dxy()
    fetch_statistichecoronavirus()
    merge_data()

    sort_data()
    report_data()

    write_geojson()
    write_csv()
