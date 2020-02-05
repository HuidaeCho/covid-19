#!/usr/bin/env python3
import requests
import pyexcel_ods3 as pyods
from io import BytesIO
import json
import config

data_url = 'https://docs.google.com/spreadsheets/d/1UF2pSkFTURko2OvfHWWlFpDFAr1UxCBA4JLwlSP6KFo/export?format=ods&id=1UF2pSkFTURko2OvfHWWlFpDFAr1UxCBA4JLwlSP6KFo'

geocode_province_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&adminDistrict={{province}}&key={config.bing_maps_key}'
geocode_country_url = f'http://dev.virtualearth.net/REST/v1/Locations?countryRegion={{country}}&key={config.bing_maps_key}'

data_ods = 'data.ods'
data_json = 'data.json'
geodata_json = 'geodata.json'

res = requests.get(data_url)
io = BytesIO(res.content)

f = open(data_ods, 'wb')
f.write(res.content)
f.close()
ods = pyods.get_data(data_ods)

#ods = pyods.get_data(io)

confirmed_sheet = ods['Confirmed']
recovered_sheet = ods['Recovered']
deaths_sheet = ods['Death']

headers = confirmed_sheet[0]

coors = {}
data = []

for i in range(1, len(confirmed_sheet)):
    cols = confirmed_sheet[i]
    if len(cols) == 0:
        continue
    province = cols[0]
    country = cols[1]
    first_confirmed_date = f'{cols[2]}'

    if config.geocode:
        if province == '':
            location = country
            geocode_url = geocode_country_url.format(country=country)
        else:
            location = f'{country},{province}'
            geocode_url = geocode_province_url.format(country=country, province=province)
        if not location in coors:
            res = requests.get(geocode_url, headers={'referer': config.bing_maps_referer})
            ret = res.json()
            resources = ret['resourceSets'][0]['resources']
            if len(resources):
                coor = resources[0]['geocodePoints'][0]['coordinates']
                latitude = coor[0]
                longitude = coor[1]
            else:
                latitude = cols[3]
                longitude = cols[4]
            coors[location] = {'latitude': latitude, 'longitude': longitude}
        else:
            latitude = coors[location].latitude
            longitude = coors[location].longitude
    else:
        latitude = cols[3]
        longitude = cols[4]

    confirmed = []
    recovered = []
    deaths = []
    for j in range(5, len(cols)):
        time = f'{headers[j]}'

        count = cols[j]
        confirmed.append({
            'time': time,
            'count': count
        })

        recovered_cols = recovered_sheet[i]
        count = recovered_cols[j] if len(recovered_cols) > j else ''
        recovered.append({
            'time': time,
            'count': count
        })

        deaths_cols = deaths_sheet[i]
        count = deaths_cols[j] if len(deaths_cols) > j else ''
        deaths.append({
            'time': time,
            'count': count
        })
    data.append({
        'country': country,
        'province': province,
        'first_confirmed_date': first_confirmed_date,
        'latitude': latitude,
        'longitude': longitude,
        'confirmed': confirmed,
        'recovered': recovered,
        'deaths': deaths
    })

f = open(data_json, 'w')
f.write(json.dumps(data))
f.close()

features = []
for rec in data:
    features.append({
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [rec['longitude'], rec['latitude']]
        },
        'properties': {
            'country': rec['country'],
            'province': rec['province'],
            'first_confirmed_date': rec['first_confirmed_date'],
            'confirmed': rec['confirmed'],
            'recovered': rec['recovered'],
            'deaths': rec['deaths']
        }
    })

geodata = {
    'type': 'FeatureCollection',
    'features': features
}

f = open(geodata_json, 'w')
f.write(json.dumps(geodata))
f.close()
