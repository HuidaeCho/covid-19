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

ts_confirmed_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv'
daily_url_format = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/{date}.csv'

features_url = 'https://services9.arcgis.com/N9p5hsImWXAccRNI/arcgis/rest/services/Nc2JKvYFoAEOFCG5JSI6/FeatureServer/1/query?where=1%3D1&outFields=*&f=json'

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

dates = []
data = []
key2data = {}
has_countries_to_display = True if len(config.countries_to_display) else False
has_duplicate_data = []
total_days = 0

def geocode(country, province, latitude=None, longitude=None):
    # TODO: admin2
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

            date = f'{year}/{month:02}/{day:02}'
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
                date = x['time'].split()[0]
                while i < total_days - 1 and dates[i] < date:
                    insert[i] = {
                        'time': f'{dates[i]} 23:59:59 UTC',
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
                    'time': f'{dates[i]} 23:59:59 UTC',
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
            if ncols == 12:
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
                admin2 = '' if row[1].strip() == 'None' else row[1].strip()
                province = '' if row[2].strip() == 'None' else row[2].strip()
                country = row[3].strip()
                # don't use last_updated; there can be duplicate entries with different counts
                last_updated = row[4]
                if row[5] and row[5] != '0':
                    latitude = round(float(row[5]), 4)
                if row[6] and row[6] != '0':
                    longitude = round(float(row[6]), 4)
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
                    latitude = round(float(row[6]), 4)
                if row[7] and row[7] != '0':
                    longitude = round(float(row[7]), 4)
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
                raise Exception(f'Unexpected format for daily report {date}')
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
                raise Exception(f'Commas are not allowed in admin2 names: {admin2} in {date}')
            if ',' in province:
                raise Exception(f'Commas are not allowed in province names: {province} in {date}')
            if ',' in country:
                raise Exception(f'Commas are not allowed in country names: {country} in {date}')
            last_updated = datetime.datetime.fromisoformat(f'{date_iso}T23:59:59+00:00')
            time_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
            key = generate_key(country, province, admin2)
            if key in dic.keymap:
                key = dic.keymap[key]
                country, province, admin2 = read_key(key)
            if key in dic.latlong:
                latlong = dic.latlong[key]
                latitude = latlong['latitude']
                longitude = latlong['longitude']
            if not latitude or not longitude:
                latitude, longitude = geocode(country, province)
                if not latitude or not longitude:
                    raise Exception(f'Latitude or longitude is not defined for {key} in {date}')
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
                    if rec['confirmed'][i]['time'] == time_str:
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
                'time': time_str,
                'count': c
            })
            recovered.insert(0, {
                'time': time_str,
                'count': r
            })
            deaths.insert(0, {
                'time': time_str,
                'count': d
            })

def fetch_all_features(features_url):
    count = 1000
    offset = 0

    features = []
    while True:
        url = f'{features_url}&resultRecordCount={count}&resultOffset={offset}'
        res = requests.get(url, headers={
            'referer': config.app_url
        })
        res = json.loads(res.content.decode())
        features.extend(res['features'])
        if 'exceededTransferLimit' not in res or res['exceededTransferLimit'] == 'false':
            break
        offset += count
    return features

def fetch_csse_rest():
    global total_days

    print('Fetching CSSE REST...')

    features = fetch_all_features(features_url)
    with open('data/csse_rest.json', 'w') as f:
        f.write(json.dumps(features))

    today_str = datetime.datetime.utcnow().strftime('%Y/%m/%d 00:00:00 UTC')

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
        province = attr['Province_State'].strip() if attr['Province_State'] else ''
        admin2 = attr['Admin2'].strip() if attr['Admin2'] else ''
        last_updated = datetime.datetime.fromtimestamp(
                attr['Last_Update']/1000, tz=datetime.timezone.utc)
        last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
        # sometimes, the last date in the CSV file is later than REST; in this
        # case, let's use today's date at 00:00:00
        if today_str > last_updated_str:
            last_updated_str = today_str
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
            latitude, longitude = geocode(country, province)
            if not latitude or not longitude:
                raise Exception(f'Latitude or longitude is not defined for {key} in {date}')
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
                'admin2': admin2,
                'latitude': latitude,
                'longitude': longitude,
                'confirmed': confirmed,
                'recovered': recovered,
                'deaths': deaths
            })

            if c:
                print(f'REST confirmed: {admin2}, {province}, {country}, 0 => {c}')
            if r:
                print(f'REST recovered: {admin2}, {province}, {country}, 0 => {r}')
            if d:
                print(f'REST deaths   : {admin2}, {province}, {country}, 0 => {d}')
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
            time_str = confirmed[len(confirmed) - 1]['time']
            # I found this case where a time from the spreadsheet is more
            # recent than the last updated time from the REST server
            if time_str > last_updated_str:
                last_updated_str = time_str

            index = len(confirmed) - 1
            c = max(confirmed[index]['count'], c)
            r = max(recovered[index]['count'], r)
            d = max(deaths[index]['count'], d)
            if c != confirmed[index]['count']:
                print(f'REST confirmed: {admin2}, {province}, {country}, {confirmed[index]["count"]} => {c}')
            if r != recovered[index]['count']:
                print(f'REST recovered: {admin2}, {province}, {country}, {recovered[index]["count"]} => {r}')
            if d != deaths[index]['count']:
                print(f'REST deaths   : {admin2}, {province}, {country}, {deaths[index]["count"]} => {d}')

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

    dates.append(today_str.split()[0])
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
    n = len(data)
    for i in range(0, n):
        rec = data[i]
        if rec['country'] != country:
            continue

        province = rec['province']
        admin2 = rec['admin2']
        if province not in dic.us_states.values() or admin2:
            # non-CONUS admin2
            if not admin2:
                rec['admin2'] = province
            continue

        # state-wide record
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

        # no admin2 records
        if len(admin2_indices) == 0:
            continue

        for j in range(0, len(confirmed)):
            c = r = d = 0
            for k in admin2_indices:
                c += data[k]['confirmed'][j]['count']
                r += data[k]['recovered'][j]['count']
                d += data[k]['deaths'][j]['count']
            if c > confirmed[j]['count']:
                confirmed[j]['count'] = c
            if r > recovered[j]['count']:
                recovered[j]['count'] = r
            if d > deaths[j]['count']:
                deaths[j]['count'] = d

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
        print('Fetching KCDC provinces 1/2 failed')
        return

    print('Fetching KCDC provinces 1/2 matched')

    country = 'South Korea'
    year = 2020
    month = int(m[1])
    day = int(m[2])
    hour = int(m[3])
    last_updated_iso = f'{year}-{month:02}-{day:02} {hour:02}:00:00+09:00'
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
    now_date = now_iso.split()[0]
    for m in matches:
        province = m[0]
        confirmed = int(m[1].replace('.', ''))
        recovered = int(m[3].replace('.', ''))
        deaths = int(m[2].replace('.', ''))

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
                if time_date != now_date:
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

    print('Fetching StatisticheCoronavirus completed')

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
                    if config.use_local_data_only:
                        date = time_str.split()[0]
                        if date not in dates:
                            dates.append(date)

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
           (country == 'United States' and
            province in dic.us_states.values() and not admin2) or \
           country == 'REMOVE':
            continue
        print(f'final: {admin2}, {province}, {country}, {latitude}, {longitude}, {c}, {r}, {d}')
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
        admin2 = rec['admin2']
        index = len(rec['confirmed']) - 1
        if (rec['confirmed'][index]['count'] +
            rec['recovered'][index]['count'] +
            rec['deaths'][index]['count'] == 0) or \
           (has_countries_to_display and
            country not in config.countries_to_display) or \
           country == 'REMOVE':
            continue
        features.append({
            'id': i,
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [rec['longitude'], rec['latitude']]
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

    # finally, build the output GeoJSON object and save it
    geodata = {
        'type': 'FeatureCollection',
        'features': features
    }

    with open(geodata_json, 'w') as f:
        f.write(json.dumps(geodata))

def write_csv():
    with open(data_csv, 'w') as f:
        f.write('admin2,province,country,latitude,longitude,category')
        for date in dates:
            date = date.replace('/', '')
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
                country not in config.countries_to_display) or \
               country == 'REMOVE':
                continue
            if ',' in admin2:
                admin2 = f'"{admin2}"'
            if ',' in province:
                province = f'"{province}"'
            if ',' in country:
                country = f'"{country}"'
            latitude = rec['latitude']
            longitude = rec['longitude']
            for category in ('confirmed', 'recovered', 'deaths'):
                f.write(f'{admin2},{province},{country},{latitude},{longitude},{category}')
                i = 0
                count = 0
                for x in rec[category]:
                    date = x['time'].split()[0]
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

        fetch_kcdc_country()
        fetch_kcdc_provinces()
        fetch_dxy()
        fetch_statistichecoronavirus()

    merge_local_data()

    sort_data()
    report_data()

    write_geojson()
    write_csv()
