/*******************************************************************************
 * Name:    covid-19.js
 * Purpose: This JavaScript file processes geodata.json and creates an
 *          interactive web map that can be embedded in index.html.
 * Author:  Huidae Cho
 * Since:   April 4, 2020
 *
 * Copyright (C) 2020, Huidae Cho <https://idea.isnew.info>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 ******************************************************************************/

function getWord(word){
	return words[word] || word;
}

let getCountText = getTextFunctions['count'] || function(count){
	return count.toLocaleString();
}

let getConfirmedText = getTextFunctions['confirmed'] || function(confirmed){
	return getCountText(confirmed) + ' ' + getWord('confirmed');
};

let getRecoveredText = getTextFunctions['recovered'] || function(recovered){
	return getCountText(recovered) + ' ' + getWord('recovered');
};

let getDeathsText = getTextFunctions['deaths'] || function(deaths){
	return getCountText(deaths) + ' ' +
		getWord('death' + (deaths > 1 ? 's' : ''));
};

let getActiveText = getTextFunctions['active'] || function(active){
	return getCountText(active) + ' ' + getWord('active');
};

function getColor(category, opacity=null){
	let color = window.getComputedStyle(
		document.getElementsByClassName(category)[0]).backgroundColor;
	if(opacity != null)
		color = color.replace(/,[^,]*\)/, ', ' + opacity + ')');
	return color;
}

function calculateConfirmedRadius(confirmed){
	return 3 * Math.log10(confirmed + 1) * (isMobile ? 0.5 : 1);
}

function createStyle(feature, resolution){
	const radiusFactor = Math.log10(maxResolution / resolution) * 0.5 + 1;
	const country = feature.get('country');
	const province = feature.get('province');
	const admin2 = feature.get('admin2');

	if((countryToDisplay && country != countryToDisplay) ||
	   (country == 'United States' && !admin2) ||
	   (country != 'United States' &&
	    hasDuplicateData.indexOf(country) >= 0 && !province))
		return null;

	const lastIndex = feature.get('confirmed').length - 1;
	const confirmed = feature.get('confirmed')[lastIndex].count;
	const recovered = feature.get('recovered')[lastIndex].count;
	const deaths = feature.get('deaths')[lastIndex].count;

	let style;
	if(true){
		const confirmedRadius = calculateConfirmedRadius(confirmed) *
			radiusFactor;
		const recoveredRadius = Math.sqrt((recovered + deaths) / confirmed) *
			confirmedRadius * radiusFactor;
		const deathsRadius = Math.sqrt(deaths / confirmed) * confirmedRadius *
			radiusFactor;
		const minOpacity = 0.05;
		const maxOpacity = 0.4;
		const opacity = minOpacity + (maxOpacity - minOpacity) *
			(confirmed - recovered - deaths) / confirmed;
		const stroke = resolution > 4000 ? null : new ol.style.Stroke({
			color: 'rgba(85, 85, 85, ' + 2 * opacity + ')'
		});
		style = [
			new ol.style.Style({
				image: new ol.style.Circle({
					radius: confirmedRadius,
					fill: new ol.style.Fill({
						color: getColor('confirmed', opacity)
					}),
					stroke: stroke
				})
			}),
			new ol.style.Style({
				image: new ol.style.Circle({
					radius: recoveredRadius,
					fill: new ol.style.Fill({
						color: getColor('recovered', opacity)
					}),
					stroke: stroke
				})
			}),
			new ol.style.Style({
				image: new ol.style.Circle({
					radius: deathsRadius,
					fill: new ol.style.Fill({
						color: getColor('deaths', 2 * opacity)
					}),
					stroke: stroke
				})
			})
		];
	}else{
		const data = [recovered, confirmed - recovered - deaths, deaths];
		const radius = calculateConfirmedRadius(confirmed) * radiusFactor;
		style = new ol.style.Style({
			image: new ol.style.Chart({
				type: 'pie',
				radius: radius,
				data: data,
				colors: [getColor('recovered'), getColor('confirmed'),
					     getColor('deaths')],
				stroke: new ol.style.Stroke({
					color: '#0000',
					width: 1
				})
			})
		});
	}
	return style;
}

function createLinks(country, province, admin2, featureId, isPopup){
	const admin2Query = admin2 ?
		admin2 + ', ' + province + ', ' + country : null;
	const provinceQuery = province ? province + ', ' + country : null;
	const admin2Text = getWord(admin2);
	const provinceText = getWord(province);
	const countryText = getWord(country);
	const links = featureId != null ?
		(!admin2 ? '' :
			'<a onclick="showFeatureStatsById(' + featureId + ')">' +
			admin2Text + '</a>, ') +
		(!province ? '' :
			'<a onclick="' +
			(admin2 ? (isPopup ? 'keepPopupOpen=true;' : '') +
				'showFeatureStatsByQuery(\'' + provinceQuery + '\')' :
				'showFeatureStatsById(' + featureId + ')') +
			'">' + provinceText + '</a>' + (countryToDisplay ? '' : ', ')) +
		(countryToDisplay ? '' :
			'<a onclick="' +
			(province ? (isPopup ? 'keepPopupOpen=true;' : '') +
				'showFeatureStatsByQuery(\'' + country + '\')' :
				'showFeatureStatsById(' + featureId + ')') +
			'">' + country + '</a>') :
		(!province ? '' :
			'<a onclick="showFeatureStatsByQuery(\'' +
			provinceQuery + '\')">' + provinceText + '</a>, ') +
		'<a onclick="showFeatureStatsByQuery(\'' + country + '\')">' +
		countryText + '</a>';
	return links;
}

let highlightedFeatureIds = [];
function highlightProvinceStats(featureIds){
	highlightedFeatureIds.forEach(featureId => {
		document.getElementById('feature-' + featureId).
			classList.remove('highlighted');
	});
	highlightedFeatureIds = featureIds;
	highlightedFeatureIds.forEach(featureId => {
		document.getElementById('feature-' + featureId).
			classList.add('highlighted');
	});
}

const timezoneOffset = new Date().getTimezoneOffset() * 60000;
function getDate(time){
	return new Date(time * 1000 - timezoneOffset).toISOString().split('T')[0];
}

function calculateStats(feature, all=false){
	const featureId = feature.id;
	const country = feature.properties.country;
	const province = feature.properties.province;
	const admin2 = feature.properties.admin2;
	const confirmed = feature.properties.confirmed;
	const recovered = feature.properties.recovered;
	const deaths = feature.properties.deaths;

	const time = [];
	const confirmedCount = [];
	const recoveredCount = [];
	const deathsCount = [];

	for(let i = 0; i <= confirmed.length - 1; i++){
		const c = confirmed[i].count;
		const r = recovered[i].count;
		const d = deaths[i].count;
		if(all || time.length || c || r || d){
			// https://stackoverflow.com/a/50130338
			time.push(getDate(confirmed[i].time));
			confirmedCount.push(c);
			recoveredCount.push(r);
			deathsCount.push(d);
		}
	}

	return {
		featureId: featureId,
		country: country,
		province: province,
		admin2: admin2,
		lastUpdated: confirmed[confirmed.length-1].time * 1000,
		time: time,
		confirmed: confirmedCount,
		recovered: recoveredCount,
		deaths: deathsCount
	};
}

function roundCFR(cfrFraction){
	return Math.round(cfrFraction * 1000) / 10;
}

function showPopup(stats, coor){
	const featureId = stats.featureId;
	const country = stats.country;
	const province = stats.province;
	const admin2 = stats.admin2;
	const time = stats.time;
	const confirmedCount = stats.confirmed;
	const recoveredCount = stats.recovered;
	const deathsCount = stats.deaths;
	const lastUpdated = stats.lastUpdated;
	const lastIndex = confirmedCount.length - 1;
	const lastConfirmed = confirmedCount[lastIndex];
	const lastRecovered = recoveredCount[lastIndex];
	const lastDeaths = deathsCount[lastIndex];

	let start = -1;
	if(confirmedCount[lastIndex])
		while(start < confirmedCount.length - 1 && !confirmedCount[++start]);
	else if(recoveredCount[lastIndex])
		while(start < recoveredCount.length - 1 && !recoveredCount[++start]);
	else if(deathsCount[lastIndex])
		while(start < deathsCount.length - 1 && !deathsCount[++start]);

	const T = lastIndex - averageDaysFromConfirmedToDeath < start ?
		lastIndex - start : averageDaysFromConfirmedToDeath;
	const lastCFRt = roundCFR(lastDeaths / confirmedCount[lastIndex - T]);

	// United States and Chile don't have recovered at a province or admin2
	// level
	const lastCFRddr = (country == 'United States' && (province || admin2)) ||
		(country == 'Chile' && province) ? null :
		roundCFR(lastDeaths / (lastDeaths + lastRecovered));

	const content =
		'<div id="popup"><h3>' +
			createLinks(country, province, admin2, featureId, true) + '</h3>' +
		'<div id="popup-last-updated">' +
			new Date(lastUpdated).toLocaleString() + '</div>' +
		'<table id="popup-stats">' +
		(!lastConfirmed ? '' :
			'<tr class="confirmed"><td>' + getWord('Confirmed') +
			':</td><td class="numeric">' + getCountText(lastConfirmed) +
			'</td></tr>') +
		(!lastRecovered ? '' :
			'<tr class="recovered"><td>' + getWord('Recovered') +
			':</td><td class="numeric">' + getCountText(lastRecovered) +
			'</td></tr>') +
		(!lastDeaths ? '' :
			'<tr class="deaths"><td>' + getWord('Deaths') +
			':</td><td class="numeric">' + getCountText(lastDeaths) +
			'</td></tr>') +
		'</table>' +
		'<div class="cfr">' + getWord('CFR') +
			'<sup><a href="https://' +
			'www.worldometers.info/coronavirus/coronavirus-death-rate/' +
			'"><span class="iconify" data-icon="fa:external-link"></span></a>' +
			'</sup>: ' +
		(lastCFRt ? '<sup>T=' + T + '</sup>' + lastCFRt + '%' +
			(isMobile || !lastCFRddr ? '' : ', ') : '') +
		(lastCFRddr ? '<sup>d/(d+r)</sup>' + lastCFRddr + '%' : '') +
		'</div>' +
		'<div id="popup-plots"></div>' +
		'<div id="popup-plots-menu" class="plots-menu"></div>' +
		'<div id="popup-plot"></div></div>' +
		'</div>';

	// XXX: why does popup.show() trigger a singleclick event when an
	// aggregating query link is clicked from the popup? this extra event
	// closes the popup window later that is shown by this function;
	// keepPopupOpen is a workaround; again, this problem only occurs with
	// aggregating links such as provinces for countries with duplicate
	// data; these stats have undefined featureId
	popup.show(coor, content);

	const confirmedIncrease = [];
	const recoveredIncrease = [];
	const deathsIncrease = [];
	const cfrT = [];
	// United States doesn't have recovered at a province or admin2 level
	const cfrDDR = lastCFRddr == null ? null : [];

	for(let i = start; i < time.length; i++){
		confirmedIncrease.push(confirmedCount[i] -
			(i > 0 ? confirmedCount[i - 1] : 0));
		recoveredIncrease.push(recoveredCount[i] -
			(i > 0 ? recoveredCount[i - 1] : 0));
		deathsIncrease.push(deathsCount[i] - (i > 0 ? deathsCount[i - 1] : 0));
		cfrT.push(i >= start + T ?
			roundCFR(deathsCount[i] / confirmedCount[i - T]) : null);
		if(cfrDDR)
			cfrDDR.push(deathsCount[i] + recoveredCount[i] ?
				roundCFR(deathsCount[i] / (deathsCount[i] + recoveredCount[i]))
				: null);
	}

	const popupStatsEl = document.getElementById('popup-stats');

	function plotCumulative(){
		const plotType = plotCumulative.plotType;
		const trends = [];
		if(confirmedCount[lastIndex])
			trends.push({
				name: 'Confirmed',
				x: time.slice(start),
				y: confirmedCount.slice(start),
				marker: {
					color: getColor('confirmed')
				}
			});
		if(recoveredCount[lastIndex])
			trends.push({
				name: 'Recovered',
				x: time.slice(start),
				y: recoveredCount.slice(start),
				marker: {
					color: getColor('recovered')
				}
			});
		if(deathsCount[lastIndex])
			trends.push({
				name: 'Deaths',
				x: time.slice(start),
				y: deathsCount.slice(start),
				marker: {
					color: getColor('deaths')
				}
			});
		const layout = {
			yaxis: {
				type: plotType == 1 ? 'linear' : 'log'
			},
			width: popupStatsEl.offsetWidth + 5,
			height: isMobile ? 50 : 100,
			margin: {
				l: isMobile ? 20 : 30,
				r: isMobile ? 6 : 15,
				b: isMobile ? 20 : 30,
				t: 5
			},
			font: {
				size: isMobile ? 6 : 10
			},
			showlegend: false
		};
		Plotly.newPlot('popup-plot', trends, layout, {displayModeBar: false});
	}

	function plotIncrease(){
		const plotType = plotIncrease.plotType;
		const trends = [];
		if(confirmedCount[lastIndex])
			trends.push({
				name: 'Confirmed',
				x: time.slice(start),
				y: confirmedIncrease,
				marker: {
					color: getColor('confirmed')
				}
			});
		if(recoveredCount[lastIndex])
			trends.push({
				name: 'Recovered',
				x: time.slice(start),
				y: recoveredIncrease,
				marker: {
					color: getColor('recovered')
				}
			});
		if(deathsCount[lastIndex])
			trends.push({
				name: 'Deaths',
				x: time.slice(start),
				y: deathsIncrease,
				marker: {
					color: getColor('deaths')
				}
			});
		const layout = {
			yaxis: {
				type: plotType == 1 ? 'linear' : 'log'
			},
			width: popupStatsEl.offsetWidth + 5,
			height: isMobile ? 50 : 100,
			margin: {
				l: isMobile ? 20 : 30,
				r: isMobile ? 6 : 15,
				b: isMobile ? 20 : 30,
				t: 5
			},
			font: {
				size: isMobile ? 6 : 10
			},
			showlegend: false
		};
		Plotly.newPlot('popup-plot', trends, layout, {displayModeBar: false});
	}

	function plotCFR(){
		const plotType = plotCFR.plotType;
		const trends = [];
		trends.push({
			name: 'T=' + T,
			x: time.slice(start),
			y: cfrT
		});
		if(cfrDDR)
			trends.push({
				name: 'd/(d+r)',
				x: time.slice(start),
				y: cfrDDR
			});
		layout = {
			yaxis: {
				type: plotType == 1 ? 'linear' : 'log'
			},
			width: popupStatsEl.offsetWidth + 5,
			height: isMobile ? 50 : 100,
			margin: {
				l: isMobile ? 20 : 30,
				r: isMobile ? 6 : 15,
				b: isMobile ? 20 : 30,
				t: 5
			},
			font: {
				size: isMobile ? 6 : 10
			},
			showlegend: false
		};
		Plotly.newPlot('popup-plot', trends, layout, {displayModeBar: false});
	}

	const popupPlotsMenuEl = document.getElementById('popup-plots-menu');
	const plotsMenuConfig = {};
	plotsMenuItems.forEach(item => {
		if(['Cumulative', 'Increase', 'CFR'].indexOf(item) >= 0)
			plotsMenuConfig[item] = eval('plot' + item);
	});
	generatePlotsMenu(popupPlotsMenuEl, plotsMenuConfig);
}

function panToCoordinates(coor){
	view.animate({center: coor});
}

function zoomToExtent(extent){
	view.fit(ol.extent.buffer(extent, 100000), {duration: 1000});
}

function showFeatureStatsAtCoordinates(feature, coor){
	highlightProvinceStats([feature.id]);
	const stats = calculateStats(feature);
	showPopup(stats, coor);
}

function showFeatureStatsById(featureId){
	const feature = features[featureId];
	const coor = ol.proj.fromLonLat(feature.geometry.coordinates);
	panToCoordinates(coor);
	showFeatureStatsAtCoordinates(feature, coor);
}

function showFeatureStatsByQuery(query){
	const extent = new ol.extent.createEmpty();
	const featureIds = [];
	const stats = {
		time: [],
		confirmed: [],
		recovered: [],
		deaths: []
	};
	let featureId = Number(query);
	if(!isNaN(featureId) && Number.isInteger(featureId)){
		if(featureId > 0)
			featureId--;
		else if(featureId < 0)
			featureId = features.length + featureId;

		const feature = features[featureId];
		if(feature && document.getElementById('feature-' + featureId)){
			const coor = ol.proj.fromLonLat(feature.geometry.coordinates);
			ol.extent.extend(extent, [coor[0], coor[1], coor[0], coor[1]]);
			featureIds.push(featureId);
		}
	}else
		features.forEach(feature => {
			const featureId = feature.id;
			const country = feature.properties.country;
			const province = feature.properties.province;
			const admin2 = feature.properties.admin2;
			const admin2Query = admin2 + ', ' + province + ', ' + country;
			const provinceQuery = province + ', ' + country;
			const coor = ol.proj.fromLonLat(feature.geometry.coordinates);
			if(hasDuplicateData.indexOf(query) >= 0){
				if(query == country){
					if(!province){
						const s = calculateStats(feature);
						stats.lastUpdated = s.lastUpdated;
						stats.time = s.time;
						stats.confirmed = s.confirmed;
						stats.recovered = s.recovered;
						stats.deaths = s.deaths;
					}else
						featureIds.push(featureId);
				}
			}else if(admin2Query == query || admin2Query.indexOf(query) >= 0 ||
				 provinceQuery == query || provinceQuery.indexOf(query) >= 0 ||
				 (query != 'Others' && province.indexOf(query) >= 0) ||
				 country.indexOf(query) >= 0){
				const s = calculateStats(feature, true);
				if(s.confirmed[s.confirmed.length - 1] +
				   s.recovered[s.recovered.length - 1] +
				   s.deaths[s.deaths.length - 1] == 0)
					return;
				if(country == 'United States'){
					// country match
					let matchLevel = 0;
					const x = query.split(', ');
					if(admin2Query == query || admin2 == query ||
					   (x.length == 3 && admin2 == x[0]))
						// admin2 match
						matchLevel = 2;
					else if(provinceQuery == query || province == query ||
						(x.length == 2 && province == x[0]))
						// province match
						matchLevel = 1;
					// only admin2 records are displayed
					if(admin2)
						featureIds.push(featureId);
					switch(matchLevel){
					case 0: // country level
						// find the country data
						if(province || admin2)
							return;
						break;
					case 1: // province level
						// find the province data
						if(province != admin2 && admin2)
							return;
						break;
					}
					// otherwise, admin2 match and admin2 data
				}else
					featureIds.push(featureId);
				if(stats.time.length == 0){
					stats.lastUpdated = s.lastUpdated;
					stats.time = s.time;
					stats.confirmed = s.confirmed;
					stats.recovered = s.recovered;
					stats.deaths = s.deaths;
				}else{
					if(s.lastUpdated > stats.lastUpdated)
						stats.lastUpdated = s.lastUpdated;
					for(let i = stats.time.length - 1, j = s.time.length - 1;
						i >= 0 && j >= 0; i--, j--){
						stats.confirmed[i] += s.confirmed[j];
						stats.recovered[i] += s.recovered[j];
						stats.deaths[i] += s.deaths[j];
					}
				}
				ol.extent.extend(extent, [coor[0], coor[1], coor[0], coor[1]]);
			}
		});
	if(featureIds.length){
		window.location.hash = 'feature-' + featureIds[0];
		highlightProvinceStats(featureIds);
		if(featureIds.length == 1){
			zoomToExtent(extent);
			showFeatureStatsById(featureIds[0]);
		}else{
			let geocodeUrl = 'https://dev.virtualearth.net/REST/v1/Locations?' +
					'key=' + bingMapsKey + '&countryRegion=';
			let country;
			let province;
			if(query.indexOf(', ') >= 0){
				const x = query.split(', ');
				country = x[1];
				province = x[0];
				geocodeUrl += country + '&adminDistrict=' + province;
			}else{
				country = query;
				geocodeUrl += country;
			}
			const geocodeXhr = new XMLHttpRequest();
			geocodeXhr.open('GET', geocodeUrl, true);
			geocodeXhr.responseType = 'json';
			geocodeXhr.onload = function(){
				const status = geocodeXhr.status;
				if(status == 200 &&
				   geocodeXhr.response.resourceSets[0].estimatedTotal){
					const resource = geocodeXhr.response.resourceSets[0].
						resources[0];
					const coor = ol.proj.fromLonLat(
						resource.geocodePoints[0].coordinates.reverse());
					const c1 = ol.proj.fromLonLat(
						[resource.bbox[1], resource.bbox[0]]);
					const c2 = ol.proj.fromLonLat(
						[resource.bbox[3], resource.bbox[2]]);
					ol.extent.extend(extent, [c1[0], c1[1], c2[0], c2[1]]);
					stats.country = country;
					stats.province = province;
					showPopup(stats, coor);
				}else
					console.log(status);
				zoomToExtent(extent);
			};
			geocodeXhr.send();
		}
	}
}

function plotCumulative(){
	const plotType = plotCumulative.plotType;
	const trends = [];
	trends.push({
		name: 'Confirmed',
		x: time,
		y: confirmedCount,
		marker: {
			color: getColor('confirmed')
		}
	});
	trends.push({
		name: 'Recovered',
		x: time,
		y: recoveredCount,
		marker: {
			color: getColor('recovered')
		}
	});
	trends.push({
		name: 'Deaths',
		x: time,
		y: deathsCount,
		marker: {
			color: getColor('deaths')
		}
	});
	const layout = {
		yaxis: {
			type: plotType == 1 ? 'linear' : 'log'
		},
		height: isMobile ? 50 : 150,
		margin: {
			l: isMobile ? 15 : 30,
			r: isMobile ? 6 : 10,
			b: isMobile ? 20 : 30,
			t: isMobile ? 3 : 10
		},
		font: {
			size: isMobile ? 6 : 12
		},
		showlegend: false
	};
	Plotly.newPlot('plot', trends, layout, {displayModeBar: false});
}

function plotIncrease(){
	const plotType = plotIncrease.plotType;
	const trends = [];
	trends.push({
		name: 'Confirmed',
		x: time,
		y: confirmedIncrease,
		marker: {
			color: getColor('confirmed')
		}
	});
	trends.push({
		name: 'Recovered',
		x: time,
		y: recoveredIncrease,
		marker: {
			color: getColor('recovered')
		}
	});
	trends.push({
		name: 'Deaths',
		x: time,
		y: deathsIncrease,
		marker: {
			color: getColor('deaths')
		}
	});
	const layout = {
		yaxis: {
			type: plotType == 1 ? 'linear' : 'log'
		},
		height: isMobile ? 50 : 150,
		margin: {
			l: isMobile ? 15 : 30,
			r: isMobile ? 6 : 10,
			b: isMobile ? 20 : 30,
			t: isMobile ? 3 : 10
		},
		font: {
			size: isMobile ? 6 : 12
		},
		showlegend: false
	};
	Plotly.newPlot('plot', trends, layout, {displayModeBar: false});
}

function plotCFR(){
	const plotType = plotCFR.plotType;
	const trends = [];
	trends.push({
		name: 'T=' + averageDaysFromConfirmedToDeath,
		x: time,
		y: cfrT
	});
	trends.push({
		name: 'd/(d+r)',
		x: time,
		y: cfrDDR
	});
	layout = {
		yaxis: {
			type: plotType == 1 ? 'linear' : 'log'
		},
		height: isMobile ? 50 : 150,
		margin: {
			l: isMobile ? 10 : 25,
			r: isMobile ? 6 : 10,
			b: isMobile ? 20 : 30,
			t: isMobile ? 0 : 10
		},
		font: {
			size: isMobile ? 6 : 12
		},
		showlegend: false
	};
	Plotly.newPlot('plot', trends, layout, {displayModeBar: false});
}

function plotConfirmed(){
	const plotType = plotConfirmed.plotType;
	const trends = [];
	Object.entries(statsByCountry).forEach(([country, stats]) => {
		const confirmed = stats.confirmed;
		if(plotType % 2){
			trends.push({
				name: country,
				x: stats.time,
				y: confirmed
			});
		}else{
			let start = -1;
			while(start < confirmed.length - 1 && !confirmed[++start]);
			trends.push({
				name: country,
				y: confirmed.slice(start)
			});
		}
	});
	const layout = {
		yaxis: {
			type: plotType <= 2 ? 'linear' : 'log'
		},
		height: isMobile ? 50 : 150,
		margin: {
			l: isMobile ? 15 : 30,
			r: isMobile ? 6 : 10,
			b: plotType % 2 ? (isMobile ? 20 : 30) : (isMobile ? 10 : 15),
			t: isMobile ? 3 : 10
		},
		font: {
			size: isMobile ? 6 : 12
		},
		showlegend: false
	};
	Plotly.newPlot('plot', trends, layout, {displayModeBar: false});
}

function plotRecovered(){
	const plotType = plotRecovered.plotType;
	const trends = [];
	Object.entries(statsByCountry).forEach(([country, stats]) => {
		const recovered = stats.recovered;
		if(plotType % 2){
			trends.push({
				name: country,
				x: time,
				y: recovered
			});
		}else{
			let start = -1;
			while(start < recovered.length - 1 && !recovered[++start]);
			trends.push({
				name: country,
				y: recovered.slice(start)
			});
		}
	});
	const layout = {
		yaxis: {
			type: plotType <= 2 ? 'linear' : 'log'
		},
		height: isMobile ? 50 : 150,
		margin: {
			l: isMobile ? 15 : 30,
			r: isMobile ? 6 : 10,
			b: plotType % 2 ? (isMobile ? 20 : 30) : (isMobile ? 10 : 15),
			t: isMobile ? 3 : 10
		},
		font: {
			size: isMobile ? 6 : 12
		},
		showlegend: false
	};
	Plotly.newPlot('plot', trends, layout, {displayModeBar: false});
}

function plotDeaths(){
	const plotType = plotDeaths.plotType;
	const trends = [];
	Object.entries(statsByCountry).forEach(([country, stats]) => {
		const deaths = stats.deaths;
		if(plotType % 2){
			trends.push({
				name: country,
				x: time,
				y: deaths
			});
		}else{
			let start = -1;
			while(start < deaths.length - 1 && !deaths[++start]);
			trends.push({
				name: country,
				y: deaths.slice(start)
			});
		}
	});
	const layout = {
		yaxis: {
			type: plotType <= 2 ? 'linear' : 'log'
		},
		height: isMobile ? 50 : 150,
		margin: {
			l: isMobile ? 15 : 30,
			r: isMobile ? 6 : 10,
			b: plotType % 2 ? (isMobile ? 20 : 30) : (isMobile ? 10 : 15),
			t: isMobile ? 3 : 10
		},
		font: {
			size: isMobile ? 6 : 12
		},
		showlegend: false
	};
	Plotly.newPlot('plot', trends, layout, {displayModeBar: false});
}

function generatePlotsMenu(menuEl, menuConfig){
	menuEl.innerHTML = '';
	let first = true;
	Object.entries(menuConfig).forEach(([title, callback]) => {
		function myCallback(a, wasActive){
			if(wasActive){
				callback.plotType++;
				if(callback.plotType > callback.plotTypes)
					callback.plotType = 1;
			}
			a.innerHTML = getWord(title) +
				'<sup>' + callback.plotType + '</sup>';
			callback();
		}

		const a = document.createElement('a');
		callback.plotType = 1;
		callback.plotTypes = ['Confirmed', 'Recovered', 'Deaths'].
			indexOf(title) >= 0 ? 4 : 2;
		a.innerHTML = getWord(title) + '<sup>' + callback.plotType + '</sup>';
		a.onclick = function(){
			const wasActive = this.classList.contains('active');
			menuEl.childNodes.forEach(node => {
				if(node.innerHTML == this.innerHTML)
					node.classList.add('active');
				else
					node.classList.remove('active');
			});
			myCallback(this, wasActive);
		};
		menuEl.appendChild(a);

		if(first){
			a.classList.add('active');
			myCallback(a, false);
			first = false;
		}
	});
}

const statsByCountry = {};
const time = [];
const confirmedCount = [];
const recoveredCount = [];
const deathsCount = [];
const confirmedIncrease = [];
const recoveredIncrease = [];
const deathsIncrease = [];
const cfrT = [];
const cfrDDR = [];
function showGlobalStats(panToMaxConfirmed){
	let lastUpdated = 0;
	let statsByProvince = '';
	let maxActive = 0;
	let maxConfirmedCoor;
	const extent = countryToDisplay ? new ol.extent.createEmpty() : null;
	features.forEach(feature => {
		const featureId = feature.id;
		const country = feature.properties.country;
		const province = feature.properties.province;
		const admin2 = feature.properties.admin2;
		const latitude = feature.geometry.coordinates[1];
		const longitude = feature.geometry.coordinates[0];
		const confirmed = feature.properties.confirmed;
		const recovered = feature.properties.recovered;
		const deaths = feature.properties.deaths;
		const updated = confirmed[confirmed.length-1].time * 1000;
		const lastIndex = confirmed.length - 1;
		const lastConfirmed = confirmed[lastIndex].count;
		const lastRecovered = recovered[lastIndex].count;
		const lastDeaths = deaths[lastIndex].count;

		if((countryToDisplay && country != countryToDisplay) ||
		   (!lastConfirmed && !lastRecovered && !lastDeaths))
			return;

		if((country == 'United States' && admin2) ||
		   (country != 'United States' &&
		    (hasDuplicateData.indexOf(country) < 0 || province))){
			// country statistics
			statsByProvince +=
				'<div id="feature-' + featureId +
					'" class="stats-by-province">' +
				'<div>' + createLinks(country, province, admin2, featureId,
									  false) + '</div>' +
				'<div onclick="showFeatureStatsById(' + featureId + ')">';
			if(lastConfirmed)
				statsByProvince += '<div class="confirmed">' +
					getConfirmedText(lastConfirmed) + '</div>';
			if(lastRecovered)
				statsByProvince += '<div class="recovered">' +
					getRecoveredText(lastRecovered) + '</div>';
			if(lastDeaths)
				statsByProvince += '<div class="deaths">' +
					getDeathsText(lastDeaths) + '</div>';
			statsByProvince += '</div></div>';

			if(updated > lastUpdated)
				lastUpdated = updated;

			if(countryToDisplay){
				const coor = ol.proj.fromLonLat(feature.geometry.coordinates);
				ol.extent.extend(extent, [coor[0], coor[1], coor[0], coor[1]]);
				const name = province || country;

				statsByCountry[name] =
					{time: [], confirmed: [], recovered: [], deaths: []};
				for(let i = 0; i < confirmed.length; i++){
					const t = confirmed[i].time;
					const c = confirmed[i].count;
					const r = recovered[i].count;
					const d = deaths[i].count;

					// province statistics
					statsByCountry[name].time.push(getDate(t));
					statsByCountry[name].confirmed.push(c);
					statsByCountry[name].recovered.push(r);
					statsByCountry[name].deaths.push(d);
				}
			}

			// don't double count for global statistics
			if(country == 'United States' ||
			   hasDuplicateData.indexOf(country) >= 0)
				return;
		}else if(country == 'United States' && province)
			return;

		// global statistics
		if(updated > lastUpdated)
			lastUpdated = updated;

		if(!countryToDisplay && !statsByCountry[country])
			statsByCountry[country] =
				{time: [], confirmed: [], recovered: [], deaths: []};

		for(let i = 0; i < confirmed.length; i++){
			const t = confirmed[i].time;
			const c = confirmed[i].count;
			const r = recovered[i].count;
			const d = deaths[i].count;

			if(!countryToDisplay){
				// country statistics
				if(statsByCountry[country].confirmed.length < confirmed.length){
					statsByCountry[country].time.push(getDate(t));
					statsByCountry[country].confirmed.push(c);
					statsByCountry[country].recovered.push(r);
					statsByCountry[country].deaths.push(d);
				}else{
					statsByCountry[country].confirmed[i] += c;
					statsByCountry[country].recovered[i] += r;
					statsByCountry[country].deaths[i] += d;
				}
			}

			// global statistics
			if(i + 1 > time.length){
				// https://stackoverflow.com/a/50130338
				time.push(getDate(confirmed[i].time));
				confirmedCount.push(c);
				recoveredCount.push(r);
				deathsCount.push(d);
			}else{
				confirmedCount[i] += c;
				recoveredCount[i] += r;
				deathsCount[i] += d;
			}
			if(i == confirmed.length - 1 &&
			   confirmedCount.length > confirmed.length){
				const k = confirmedCount.length - 1;
				confirmedCount[k] += c;
				recoveredCount[k] += r;
				deathsCount[k] += d;
			}
		}

		if(lastConfirmed - lastRecovered - lastDeaths > maxActive){
			maxActive = lastConfirmed - lastRecovered - lastDeaths;
			maxConfirmedCoor = [longitude, latitude];
		}
	});
	Object.entries(statsByCountry).forEach(([country, stats]) => {
		const lastIndex = stats.confirmed.length - 1;
		const confirmed = stats.confirmed[lastIndex];
		const recovered = stats.recovered[lastIndex];
		const deaths = stats.deaths[lastIndex];
		sortedByCountry.push({
			country: country,
			confirmed: confirmed,
			recovered: recovered,
			deaths: deaths,
			active: confirmed - recovered - deaths,
			cfrDDR: roundCFR(deaths / (deaths + recovered))
		});
	});

	statsByProvinceEl.innerHTML = statsByProvince;

	for(let i = 0; i < time.length; i++){
		confirmedIncrease.push(confirmedCount[i] -
			(i > 0 ? confirmedCount[i - 1] : 0));
		recoveredIncrease.push(recoveredCount[i] -
			(i > 0 ? recoveredCount[i - 1] : 0));
		deathsIncrease.push(deathsCount[i] - (i > 0 ? deathsCount[i - 1] : 0));
		cfrT.push(i >= averageDaysFromConfirmedToDeath ?
			roundCFR(deathsCount[i] /
				confirmedCount[i - averageDaysFromConfirmedToDeath]) : null);
		cfrDDR.push(deathsCount[i] + recoveredCount[i] ?
			roundCFR(deathsCount[i] /
				(deathsCount[i] + recoveredCount[i])) : null);
	}

	const lastIndex = time.length - 1;
	lastUpdatedEl.innerHTML = new Date(lastUpdated).toLocaleString();
	totalConfirmedEl.innerHTML = getCountText(confirmedCount[lastIndex]);
	totalRecoveredEl.innerHTML = getCountText(recoveredCount[lastIndex]);
	totalDeathsEl.innerHTML = getCountText(deathsCount[lastIndex]);
	cfrEl.innerHTML = '<sup>T=' + averageDaysFromConfirmedToDeath + '</sup>' +
		cfrT[cfrT.length - 1] + '%' + (isMobile ? '' : ', ') +
		'<sup>d/(d+r)</sup>' + cfrDDR[cfrDDR.length - 1] + '%';

	const plotsMenuConfig = {};
	plotsMenuItems.forEach(item => {
		if(isMobile && ['Confirmed', 'Recovered', 'Deaths'].indexOf(item) >= 0)
			return;
		plotsMenuConfig[item] = eval('plot' + item);
	});
	generatePlotsMenu(plotsMenuEl, plotsMenuConfig);

	statsByProvinceEl.style.height = (bodyHeight - headerEl.offsetHeight -
		summaryEl.offsetHeight - plotsEl.offsetHeight - 6) + 'px';

	if(panToMaxConfirmed){
		if(extent)
			zoomToExtent(extent);
		else
			panToCoordinates(ol.proj.fromLonLat(maxConfirmedCoor));
	}
}

let sortDescending = true;
function sortStatsByCountry(category){
	let nextCategory;
	sortedByCountry.sort(function(a, b){
		switch(category){
		case 'Confirmed':
			nextCategory = 'Recovered';
			a = a.confirmed;
			b = b.confirmed;
			break;
		case 'Recovered':
			nextCategory = 'Deaths';
			a = a.recovered;
			b = b.recovered;
			break;
		case 'Deaths':
			nextCategory = 'Active';
			a = a.deaths;
			b = b.deaths;
			break;
		case 'Active':
			nextCategory = 'CFR d/(d+r)';
			a = a.active;
			b = b.active;
			break;
		case 'CFR d/(d+r)':
			nextCategory = 'Confirmed';
			a = a.cfrDDR;
			b = b.cfrDDR;
			break;
		}
		return sortDescending ? b - a : a - b;
	});
	countryLinksEl.innerHTML =
		'<a onclick="sortDescending=!sortDescending;sortStatsByCountry(\'' +
			category +
			'\')"><span class="iconify" data-icon="icomoon-free:sort-amount-' +
			(sortDescending ? 'desc' : 'asc') + '"></span></a> ' +
		'<a onclick="sortStatsByCountry(\'' + nextCategory + '\')">' +
			getWord(category) + '</a>: ';
	for(let i = 0; i < sortedByCountry.length; i++){
		const country = sortedByCountry[i].country;
		const backup = countryLinksEl.innerHTML;
		const popup =
			getConfirmedText(sortedByCountry[i].confirmed) + ', ' +
			getRecoveredText(sortedByCountry[i].recovered) + ', ' +
			getDeathsText(sortedByCountry[i].deaths) + ', ' +
			getActiveText(sortedByCountry[i].active) + ', ' +
			getWord('CFR') + ' d/(d+r) ' +
				sortedByCountry[i].cfrDDR.toLocaleString() + '%';
		countryLinksEl.innerHTML += (i > 0 ? ', ' : '') +
			'<a onclick="showFeatureStatsByQuery(\'' + country +
				(countryToDisplay ? ', ' + countryToDisplay : '') +
				'\')" title="' + popup + '">' + getWord(country) + '</a>' +
			'<sup><a href="?' +
				(country + (countryToDisplay ? ', ' + countryToDisplay : '')).
					replace(/ /g, '%20') + '" title="' + popup + '">' +
			'<span class="iconify" data-icon="fa:link"></span>' +
			'</a></sup>';
		if(countryLinksEl.offsetWidth > headerEl.offsetWidth - 10){
			countryLinksEl.innerHTML = backup;
			break;
		}
	}
}

/*******************************************************************************
 * ELEMENTS
 ******************************************************************************/

const isMobile = window.getComputedStyle(
	document.getElementsByClassName('mobile-block')[0]).display == 'block';
const bodyEl = document.body;
const headerEl = document.getElementById('header');
const countryLinksEl = document.getElementById('country-links');
const mapEl = document.getElementById('map');
const infoEl = document.getElementById('info');
const lastUpdatedEl = document.getElementById('last-updated');
const totalConfirmedEl = document.getElementById('total-confirmed');
const totalRecoveredEl = document.getElementById('total-recovered');
const totalDeathsEl = document.getElementById('total-deaths');
const cfrEl = document.getElementById('cfr');
const summaryEl = document.getElementById('summary');
const plotsEl = document.getElementById('plots');
const plotsMenuEl = document.getElementById('plots-menu');
const statsByProvinceEl = document.getElementById('stats-by-province');
const bodyStyle = window.getComputedStyle(bodyEl);
const bodyWidth = Number(bodyStyle.width.replace('px', ''));
const bodyHeight = Number(bodyStyle.height.replace('px', ''));

/*******************************************************************************
 * ADJUST MAP SIZE
 ******************************************************************************/

mapEl.style.height = (bodyHeight - headerEl.offsetHeight -
	(isMobile ? 0 : 8)) + 'px';
mapEl.style.width = (bodyWidth - infoEl.offsetWidth -
	(isMobile ? 4 : 6)) + 'px';

/*******************************************************************************
 * CREATE MAP
 ******************************************************************************/

const popup = new ol.Overlay.Popup();
const map = new ol.Map({
	target: 'map',
	controls: ol.control.defaults().extend([
		new ol.control.ScaleLine({units: mapUnits})]),
	layers: [
		new ol.layer.Group({
			title: getWord('Base maps'),
			openInLayerSwitcher: true,
			layers: [
				new ol.layer.Group({
					title: getWord('Water color'),
					baseLayer: true,
					combine: true,
					layers: [
						new ol.layer.Tile({
							title: getWord('Base map'),
							source: new ol.source.Stamen({
								layer: 'watercolor'
							})
						}),
						new ol.layer.Tile({
							title: getWord('Labels'),
							source: new ol.source.Stamen({
								layer: 'terrain-labels'
							})
						})
					],
					visible: false
				}),
				new ol.layer.Tile({
					title: getWord('Bing aerial'),
					baseLayer: true,
					source: new ol.source.BingMaps({
						key: bingMapsKey,
						imagerySet: 'AerialWithLabelsOnDemand',
					}),
					visible: false
				}),
				new ol.layer.Tile({
					title: getWord('Open Street'),
					baseLayer: true,
					source: new ol.source.OSM()
				})
			]
		}),
		new ol.layer.Vector({
			title: getWord('COVID-19 cases'),
			source: new ol.source.Vector({
				format: new ol.format.GeoJSON(),
				url: dataUrl,
				attributions: '&copy; ' + getWord('Data sources') + ': ' +
					dataSources
			}),
			style: function(feature, resolution){
				return createStyle(feature, resolution);
			}
		})
	],
	view: new ol.View({
		center: ol.proj.fromLonLat([37.41, 8.82]),
		zoom: 1,
	}),
	overlays: [popup],
});
map.addControl(new ol.control.LayerSwitcher());
map.on('pointermove', function(evt){
	map.getTargetElement().style.cursor =
		map.hasFeatureAtPixel(evt.pixel) ? 'pointer' : '';
});
let keepPopupOpen = false;
map.on('singleclick', function(evt){
	const feature = map.forEachFeatureAtPixel(evt.pixel,
		function(feature, layer){
			return features[feature.getId()];
		});
	if(feature){
		window.location.hash = 'feature-' + feature.id;
		showFeatureStatsAtCoordinates(feature, evt.coordinate);
	}else if(keepPopupOpen)
		keepPopupOpen = false;
	else{
		highlightProvinceStats([]);
		popup.hide();
	}
});
const view = map.getView();
const maxResolution = view.getResolution();

/*******************************************************************************
 * POPULATE GLOBAL TOTAL
 ******************************************************************************/

let features;
const sortedByCountry = [];
const xhr = new XMLHttpRequest();
xhr.open('GET', dataUrl, true);
xhr.responseType = 'json';
xhr.onload = function(){
	const status = xhr.status;
	if(status == 200){
		features = xhr.response.features;
		const queryMatches = window.location.search.match(/^\?(.+)$/);

		showGlobalStats(!queryMatches);
		sortStatsByCountry('Confirmed');

		if(queryMatches){
			const query = queryMatches[1].replace(/\+|%20/g, ' ').
				replace(/%22/g, '"');
			showFeatureStatsByQuery(query);
		}
	}else
		console.log(status);
};
xhr.send();
