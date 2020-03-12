#!/usr/bin/env python3
import requests
import io
import csv
import json
import datetime
import re
import os
import glob
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
dxy_re = '"createTime":([0-9]+),.*window\.getAreaStat = (.*?)\}catch\(e\)'

geocode_province_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{province}}&key={config.bing_maps_key}'
geocode_country_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&key={config.bing_maps_key}'

geodata_json = 'geodata.json'

# use this dictionary to avoid geocoding the same province multiple times
coors_json = 'coors.json'

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
    global south_korea_index

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

        # for each province
        for confirmed_row in confirmed_reader:
            recovered_row = recovered_reader.__next__()
            deaths_row = deaths_reader.__next__()

            if len(confirmed_row) < num_cols:
                continue

            col = 0
            province = confirmed_row[col]; col += 1
            province = '' if province == 'None' else province
            country = confirmed_row[col]; col += 1

            # retrieve coordinates from the geocoding server if desired;
            # otherwise, just use coordinates from the spreadsheet
            latitude = float(confirmed_row[col]); col += 1
            longitude = float(confirmed_row[col]); col += 1
            if config.geocode:
                latitude, longitude = geocode(country, province,
                        latitude, longitude)
            latitude = round(latitude, 4)
            longitude = round(longitude, 4)

            if 'Diamond Princess' in province:
                key = f'{province},{country}'
            else:
                key = f'{latitude},{longitude}'
            if key not in key2data:
                key2data[key] = len(data)
                if key == '36.0,128.0':
                    south_korea_index = key2data[key]
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
                confirmed = data[key2data[key]]['confirmed']
                recovered = data[key2data[key]]['recovered']
                deaths = data[key2data[key]]['deaths']
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
                    confirmed[j - col]['count'] += c
                    recovered[j - col]['count'] += r
                    deaths[j - col]['count'] += d

    print('Fetching CSSE CSV completed')

def fetch_csse_rest():
    print('Fetching CSSE REST...')

    res = requests.get(features_url)

    with open('data/csse_rest.json', 'w') as f:
        f.write(res.content.decode())

    features = json.loads(res.content)['features']

    # try to find most up-to-date info from the REST server
    for feature in features:
        attr = feature['attributes']
        country = attr['Country_Region']
        province = attr['Province_State'] if attr['Province_State'] else ''
        latitude = round(feature['geometry']['y'], 4)
        longitude = round(feature['geometry']['x'], 4)
        last_updated = datetime.datetime.fromtimestamp(
                attr['Last_Update']/1000, tz=datetime.timezone.utc)
        last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'

        if 'Diamond Princess' in province:
            key = f'{province},{country}'
        else:
            key = f'{latitude},{longitude}'
        if key in dic.ll_rest2csv:
            key = dic.ll_rest2csv[key]
        if key not in key2data:
            # new record not in data
            key2data[key] = len(data)
            # create and populate three lists with REST data
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
            existing = False
        else:
            # retrieve existing lists
            confirmed = data[key2data[key]]['confirmed']
            recovered = data[key2data[key]]['recovered']
            deaths = data[key2data[key]]['deaths']
            time_str = confirmed[len(confirmed) - 1]['time']
            # I found this case where a time from the spreadsheet is more
            # recent than the last updated time from the REST server
            if time_str > last_updated_str:
                last_updated_str = time_str
            existing = True

        c = int(attr['Confirmed'])
        r = int(attr['Recovered'])
        d = int(attr['Deaths'])

        if existing:
            index = len(confirmed) - 1
            if c != confirmed[index]['count']:
                print(f'REST confirmed: {province}, {country}, {confirmed[index]["count"]} => {c}')
            if r != recovered[index]['count']:
                print(f'REST recovered: {province}, {country}, {recovered[index]["count"]} => {r}')
            if d != deaths[index]['count']:
                print(f'REST deaths   : {province}, {country}, {deaths[index]["count"]} => {d}')
        else:
            print(f'REST confirmed: {province}, {country}, {c}')
            print(f'REST recovered: {province}, {country}, {r}')
            print(f'REST deaths   : {province}, {country}, {d}')

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

    print('Fetching CSSE REST completed')

def get_data_filename(country, province=None):
    return 'data/' + (province + ', ' if province else '') + country + '.csv'

def fetch_kcdc():
    fetch_kcdc_country()
    fetch_kcdc_provinces()

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

    file = get_data_filename('South Korea')
    add_header = True
    if os.path.exists(file):
        add_header = False
        with open(file) as f:
            reader = csv.reader(f)
            for row in reader:
                pass
            time = datetime.datetime.fromisoformat(row[0]).astimezone(
                    datetime.timezone.utc)
            if time >= datetime.datetime.fromisoformat(last_updated_iso).\
                    astimezone(datetime.timezone.utc):
                return

    with open(file, 'a') as f:
        if add_header:
            f.write('time,confirmed,recovered,deaths\n')
        f.write(f'{last_updated_iso},{confirmed},{recovered},{deaths}\n')

    print('Fetching KCDC country completed')

def fetch_kcdc_provinces():
    print('Fetching KCDC provinces...')

    if not kcdc_provinces_re:
        print('Fetching KCDC provinces skipped')
        return

    print('Fetching KCDC provinces 1/2 matched')

    res = requests.get(kcdc_provinces_url).content.decode()
    m = re.search(kcdc_provinces_re, res, re.DOTALL)
    if not m:
        print('Fetching KCDC provinces 1/2 failed')
        return

    print('Fetching KCDC provinces 2/2 matched')

    year = 2020
    month = int(m[1])
    date = int(m[2])
    hour = int(m[3])
    last_updated_iso = f'{year}-{month:02}-{date:02} {hour:02}:00:00+09:00'
    matches = re.findall(kcdc_provinces_subre, m[4])
    if not matches:
        print('Fetching KCDC provinces 2/2 failed')

    for m in matches:
        province = dic.en[m[0]]
        confirmed = int(m[1].replace(',', ''))
        recovered = int(m[2].replace(',', ''))
        deaths = int(m[3].replace(',', ''))

        file = get_data_filename('South Korea', province)
        add_header = True
        if os.path.exists(file):
            add_header = False
            with open(file) as f:
                reader = csv.reader(f)
                for row in reader:
                    pass
                time = datetime.datetime.fromisoformat(row[0]).astimezone(
                        datetime.timezone.utc)
                if time >= datetime.datetime.fromisoformat(last_updated_iso).\
                        astimezone(datetime.timezone.utc):
                    continue

        with open(file, 'a') as f:
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

        country = 'Mainland China'
        if province == 'Hong Kong':
            country = f'{province} SAR'
        elif province == 'Macau':
            country = 'Macao SAR'
        elif province == 'Taiwan':
            country = 'Taipei and environs'

        file = get_data_filename(country, province)
        add_header = True
        if os.path.exists(file):
            add_header = False
            with open(file) as f:
                reader = csv.reader(f)
                reader = csv.reader(f)
                for row in reader:
                    pass
                time = datetime.datetime.fromisoformat(row[0]).astimezone(
                        datetime.timezone.utc)
                if time >= last_updated:
                    continue

        with open(file, 'w') as f:
            if add_header:
                f.write('time,confirmed,recovered,deaths\n')
            f.write(f'{last_updated_iso},{confirmed},{recovered},{deaths}\n')

    print('Fetching DXY completed')

def merge_non_csse_data():
    for rec in data:
        country = rec['country']
        province = rec['province']

        file = get_data_filename(country, province)
        if not os.path.exists(file):
            continue

        confirmed = rec['confirmed']
        recovered = rec['recovered']
        deaths = rec['deaths']
        index = len(confirmed) - 1
        time_str = confirmed[index]['time']

        with open(file) as f:
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

# create a new list for the output JSON object
data = []
# lat/long to data index
key2data = {}

fetch_csse_csv()
fetch_csse_rest()

fetch_kcdc()
fetch_dxy()

merge_non_csse_data()



#if kcdc_provinces_re:
#    c = r = d = 0
#    country = 'South Korea'
#    last_updated = None
#    for file in glob.glob('data/*, ' + country + '.csv'):
#        m = re.search('^data/(.+),.+$', file)
#        province = m[1]
#        with open(file) as f:
#            reader = csv.reader(f)
#            reader.__next__()
#            confirmed = []
#            recovered = []
#            deaths = []
#            for row in reader:
#                time = datetime.datetime.fromisoformat(row[0]).astimezone(
#                        datetime.timezone.utc)
#                if last_updated is None or time > last_updated:
#                    last_updated = time
#                time_str = f'{time.strftime("%Y/%m/%d %H:%M:%S UTC")}'
#                confirmed.append({
#                    'time': time_str,
#                    'count': int(row[1])
#                }),
#                recovered.append({
#                    'time': time_str,
#                    'count': int(row[2])
#                }),
#                deaths.append({
#                    'time': time_str,
#                    'count': int(row[3])
#                })
#            index = len(confirmed) - 1
#            c += confirmed[index]['count']
#            r += recovered[index]['count']
#            d += deaths[index]['count']
#
#            latitude, longitude = geocode(country, province)
#            latitude = round(latitude, 4)
#            longitude = round(longitude, 4)
#            data.append({
#                'country': country,
#                'province': province,
#                'latitude': latitude,
#                'longitude': longitude,
#                'confirmed': confirmed,
#                'recovered': recovered,
#                'deaths': deaths
#            })
#
#    last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
#    index = len(data[south_korea_index]['confirmed']) - 1
#    if c < data[south_korea_index]['confirmed'][index]['count'] or \
#       r < data[south_korea_index]['recovered'][index]['count'] or \
#       d < data[south_korea_index]['deaths'][index]['count']:
#           province = 'Others'
#           latitude = data[south_korea_index]['latitude']
#           longitude = data[south_korea_index]['longitude']
#           confirmed = [{
#               'time': last_updated_str,
#               'count': data[south_korea_index]['confirmed'][index]['count'] - c
#           }]
#           recovered = [{
#               'time': last_updated_str,
#               'count': data[south_korea_index]['recovered'][index]['count'] - r
#           }]
#           deaths = [{
#               'time': last_updated_str,
#               'count': data[south_korea_index]['deaths'][index]['count'] - d
#           }]
#           data.append({
#                'country': country,
#                'province': province,
#                'latitude': latitude,
#                'longitude': longitude,
#                'confirmed': confirmed,
#                'recovered': recovered,
#                'deaths': deaths
#           })
#    else:
#        data[south_korea_index]['confirmed'][index]['time'] = last_updated_str
#        data[south_korea_index]['confirmed'][index]['count'] = c
#        data[south_korea_index]['recovered'][index]['time'] = last_updated_str
#        data[south_korea_index]['recovered'][index]['count'] = r
#        data[south_korea_index]['deaths'][index]['time'] = last_updated_str
#        data[south_korea_index]['deaths'][index]['count'] = d

# sort records by confirmed, country, and province
data = sorted(data, key=lambda x: (
    -x['confirmed'][len(x['confirmed'])-1]['count'],
    x['country'],
    x['province']))

total_confirmed = total_recovered = total_deaths = 0
for i in range(0, len(data)):
#    if i == south_korea_index:
#        continue
    rec = data[i]
    index = len(rec['confirmed']) - 1
    c = rec['confirmed'][index]['count']
    r = rec['recovered'][index]['count']
    d = rec['deaths'][index]['count']
    if c == 0:
        continue
    print(f'final: {rec["province"]}; {rec["country"]}; {rec["latitude"]}; {rec["longitude"]}; {c}; {r}; {d}')
    total_confirmed += c
    total_recovered += r
    total_deaths += d

print(f'Total confirmed: {total_confirmed}')
print(f'Total recovered: {total_recovered}')
print(f'Total deaths   : {total_deaths}')

# create a new list to store all the features
features = []
# create a feature collection
for i in range(0, len(data)):
    rec = data[i]
    if rec['confirmed'][len(rec['confirmed']) - 1]['count'] == 0:
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
