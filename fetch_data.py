#!/usr/bin/env python3
import requests
import io
import csv
import json
import datetime
import re
import os
import glob
from en import en
import config

features_url = 'https://services1.arcgis.com/0MSEUqKaxRlEPj5g/ArcGIS/rest/services/ncov_cases/FeatureServer/1/query?where=1%3D1&outFields=*&f=json'

confirmed_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv'
recovered_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Recovered.csv'
deaths_url = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Deaths.csv'
kcdc_country_url = 'http://ncov.mohw.go.kr/bdBoardList_Real.do'
kcdc_country_re = '현황\(([0-9]+)\.([0-9]+)일.*?([0-9]+)시.*?기준\).*?>확진환자<.*?([0-9,]+)[^0-9]*명.*?>확진환자 격리해제<.*?([0-9,]+)[^0-9]*명.*?>사망자<.*?([0-9,]+)[^0-9]*명'
kcdc_provinces_url = 'http://ncov.mohw.go.kr/bdBoardList_Real.do?brdGubun=13'
kcdc_provinces_re = '([0-9]{4})년 ([0-9]+)월 ([0-9]+)일.*?([0-9]+)시.*기준.*?<tr class="sumline">.*?</tr>.*?(<tr>.+?)</tbody>'
kcdc_provinces_subre = '>([^>]+)</th>.*?<[^>]+?s_type1[^>]+>\s*([0-9,]+)\s*<.+?s_type3[^>]+>\s*([0-9,]+)\s*<.+?s_type4[^>]+>\s*([0-9,]+)\s*<'

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
    if not location in coors:
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

def get_data_filename(country, province=None):
    return 'data/' + (province + ', ' if province else '') + country + '.csv'

def fetch_kcdc():
    fetch_kcdc_country()
    fetch_kcdc_provinces()

def fetch_kcdc_country():
    res = requests.get(kcdc_country_url).content.decode()
    m = re.search(kcdc_country_re, res, re.DOTALL)
    if not m:
        return

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

def fetch_kcdc_provinces():
    res = requests.get(kcdc_provinces_url).content.decode()
    m = re.search(kcdc_provinces_re, res, re.DOTALL)
    if not m:
        return

    year = int(m[1])
    month = int(m[2])
    date = int(m[3])
    hour = int(m[4])
    last_updated_iso = f'{year}-{month:02}-{date:02} {hour:02}:00:00+09:00'
    for m in re.findall(kcdc_provinces_subre, m[5]):
        province = en[m[0]]
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

def fetch_dxy():
    res = requests.get(dxy_url).content.decode()
    m = re.search(dxy_re, res, re.DOTALL)
    if not m:
        return
    last_updated = datetime.datetime.fromtimestamp(int(m[1])/1000,
            tz=datetime.timezone.utc)
    last_updated_iso = f'{last_updated.strftime("%Y-%m-%d %H:%M:%S+00:00")}'
    for rec in json.loads(m[2]):
        province = rec['provinceShortName']
        if not province in en:
            return
        province = en[province]
        confirmed = rec['confirmedCount']
        recovered = rec['curedCount']
        deaths = rec['deadCount']

        country = 'Mainland China'
        if province in ('Hong Kong', 'Macau', 'Taiwan'):
            country = province

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

fetch_kcdc()
fetch_dxy()

# download features from the REST server
res = requests.get(features_url)
features = json.loads(res.content)['features']

# read existing data
if os.path.exists(geodata_json):
    with open(geodata_json) as f:
        geodata = json.load(f)
else:
    geodata = {
        'features': []
    }

# create a new list for the output JSON object
data = []

total_confirmed = total_recovered = total_deaths = 0

# download CSV files
confirmed_res = requests.get(confirmed_url)
recovered_res = requests.get(recovered_url)
deaths_res = requests.get(deaths_url)
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

    # for each province
    for confirmed_row in confirmed_reader:
        recovered_row = recovered_reader.__next__()
        deaths_row = deaths_reader.__next__()

        if len(confirmed_row) == 0:
            continue

        col = 0
        province = confirmed_row[col]; col += 1
        province = '' if province == 'None' else province
        country = confirmed_row[col]; col += 1
        if len(confirmed_row) <= col:
            continue

        # retrieve coordinates from the geocoding server if desired;
        # otherwise, just use coordinates from the spreadsheet
        latitude = float(confirmed_row[col]); col += 1
        longitude = float(confirmed_row[col]); col += 1
        if config.geocode:
            latitude, longitude = geocode(country, province,
                    latitude, longitude)

        # create and populate three lists with time series data
        confirmed = []
        recovered = []
        deaths = []
        for j in range(col, len(confirmed_row)):
            date = confirmed_header[j].split('/')
            time = datetime.datetime(2000 + int(date[2]), int(date[0]),
                    int(date[1]), 23, 59, tzinfo=datetime.timezone.utc)
            # YYYY/MM/DD UTC for iOS
            time_str = f'{time.strftime("%Y/%m/%d %H:%M:%S UTC")}'
            confirmed.append({
                'time': time_str,
                'count': int(confirmed_row[j])
            })
            recovered.append({
                'time': time_str,
                'count': int(recovered_row[j])
            })
            deaths.append({
                'time': time_str,
                'count': int(deaths_row[j])
            })

        # try to find most up-to-date info from the REST server
        for feature in features:
            attr = feature['attributes']
            if (attr['Province_State'] and \
                'Diamond Princess' in attr['Province_State']) and \
               (province + ' (From Diamond Princess)' == attr['Province_State'] or \
                (country == 'Others' and country == attr['Country_Region'])):
                province = attr['Province_State']
            # need an exact match
            if country != attr['Country_Region'] or \
               (province and province != attr['Province_State']):
                continue

            # grab new coordinates from the REST server
            latitude = feature['geometry']['y']
            longitude = feature['geometry']['x']

            last_updated = datetime.datetime.fromtimestamp(
                    attr['Last_Update']/1000, tz=datetime.timezone.utc)
            # I found this case where a time from the spreadsheet is more
            # recent than the last updated time from the REST server
            if time > last_updated:
                last_updated = time
            last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'

            c = int(attr['Confirmed'])
            r = int(attr['Recovered'])
            d = int(attr['Deaths'])

            index = len(confirmed) - 1
            if c != confirmed[index]['count']:
                print(f'REST confirmed: {province}, {country}, {confirmed[index]["count"]} => {c}')
            if r != recovered[index]['count']:
                print(f'REST recovered: {province}, {country}, {recovered[index]["count"]} => {r}')
            if d != deaths[index]['count']:
                print(f'REST deaths   : {province}, {country}, {deaths[index]["count"]} => {d}')
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

        file = get_data_filename(country, province)
        if os.path.exists(file):
            with open(file) as f:
                reader = csv.reader(f)
                for row in reader:
                    pass
                last_updated = datetime.datetime.fromisoformat(row[0]).\
                        astimezone(datetime.timezone.utc)
                if last_updated > time:
                    last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
                index = len(confirmed) - 1
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

        for feature in geodata['features']:
            props = feature['properties']
            if props['country'] == country and props['province'] == province:
                for i in range(0, min(len(confirmed), len(props['confirmed']))):
                    if confirmed[i]['time'] == props['confirmed'][i]['time']:
                        confirmed[i]['count'] = max(confirmed[i]['count'],
                                props['confirmed'][i]['count'])
                        recovered[i]['count'] = max(recovered[i]['count'],
                                props['recovered'][i]['count'])
                        deaths[i]['count'] = max(deaths[i]['count'],
                                props['deaths'][i]['count'])
                break

        data.append({
            'country': country,
            'province': province,
            'latitude': latitude,
            'longitude': longitude,
            'confirmed': confirmed,
            'recovered': recovered,
            'deaths': deaths
        })

        if country == 'South Korea':
            south_korea_index = len(data) - 1

        index = len(confirmed) - 1
        total_confirmed += confirmed[index]['count']
        total_recovered += recovered[index]['count']
        total_deaths += deaths[index]['count']

# try to find newly confirmed provinces from the REST server
for feature in features:
    attr = feature['attributes']
    country = attr['Country_Region']
    province = attr['Province_State'] if attr['Province_State'] else ''
    latitude = feature['geometry']['y']
    longitude = feature['geometry']['x']
    # Diamond Princess is a country in the REST API, but it's a
    # province in Others in the CSV files; Others in the REST API is
    # empty!
    if country == 'Others':
        continue
    # need to skip existing provinces
    found = False
    for rec in data:
        if country == rec['country']:
            if province == rec['province'] or \
               (not province and rec['province']) or \
               (abs(latitude - rec['latitude']) < 0.00001 and
                abs(longitude - rec['longitude']) < 0.00001):
                if province and not rec['province']:
                    rec['province'] = province
                found = True
                break
    if found:
        continue

    # just found a new province that is not in the spreadsheet, but is in
    # the REST server; add this record
    last_updated = datetime.datetime.fromtimestamp(attr['Last_Update']/1000,
            tz=datetime.timezone.utc)
    last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'

    c = int(attr['Confirmed'])
    r = int(attr['Recovered'])
    d = int(attr['Deaths'])

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

    print(f'REST confirmed: {province}, {country}, {c}')
    print(f'REST recovered: {province}, {country}, {r}')
    print(f'REST deaths   : {province}, {country}, {d}')

    total_confirmed += c
    total_recovered += r
    total_deaths += d

print(f'Total confirmed: {total_confirmed}')
print(f'Total recovered: {total_recovered}')
print(f'Total deaths   : {total_deaths}')

c = r = d = 0
country = 'South Korea'
last_updated = None
for file in glob.glob('data/*, ' + country + '.csv'):
    m = re.search('^data/(.+),.+$', file)
    province = m[1]
    with open(file) as f:
        reader = csv.reader(f)
        reader.__next__()
        confirmed = []
        recovered = []
        deaths = []
        for row in reader:
            time = datetime.datetime.fromisoformat(row[0]).astimezone(
                    datetime.timezone.utc)
            if last_updated is None or time > last_updated:
                last_updated = time
            time_str = f'{time.strftime("%Y/%m/%d %H:%M:%S UTC")}'
            confirmed.append({
                'time': time_str,
                'count': int(row[1])
            }),
            recovered.append({
                'time': time_str,
                'count': int(row[2])
            }),
            deaths.append({
                'time': time_str,
                'count': int(row[3])
            })
        index = len(confirmed) - 1
        c += confirmed[index]['count']
        r += recovered[index]['count']
        d += deaths[index]['count']

        latitude, longitude = geocode(country, province)
        data.append({
            'country': country,
            'province': province,
            'latitude': latitude,
            'longitude': longitude,
            'confirmed': confirmed,
            'recovered': recovered,
            'deaths': deaths
        })

last_updated_str = f'{last_updated.strftime("%Y/%m/%d %H:%M:%S UTC")}'
index = len(data[south_korea_index]['confirmed']) - 1
if c < data[south_korea_index]['confirmed'][index]['count'] or \
   r < data[south_korea_index]['recovered'][index]['count'] or \
   d < data[south_korea_index]['deaths'][index]['count']:
       province = 'Others'
       latitude = data[south_korea_index]['latitude']
       longitude = data[south_korea_index]['longitude']
       confirmed = [{
           'time': last_updated_str,
           'count': data[south_korea_index]['confirmed'][index]['count'] - c
       }]
       recovered = [{
           'time': last_updated_str,
           'count': data[south_korea_index]['recovered'][index]['count'] - r
       }]
       deaths = [{
           'time': last_updated_str,
           'count': data[south_korea_index]['deaths'][index]['count'] - d
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
else:
    data[south_korea_index]['confirmed'][index]['time'] = last_updated_str
    data[south_korea_index]['confirmed'][index]['count'] = c
    data[south_korea_index]['recovered'][index]['time'] = last_updated_str
    data[south_korea_index]['recovered'][index]['count'] = r
    data[south_korea_index]['deaths'][index]['time'] = last_updated_str
    data[south_korea_index]['deaths'][index]['count'] = d

# sort records by confirmed, country, and province
data = sorted(data, key=lambda x: (
    -x['confirmed'][len(x['confirmed'])-1]['count'],
    x['country'],
    x['province']))

# create a new list to store all the features
features = []
# create a feature collection
for i in range(0, len(data)):
    rec = data[i]
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
