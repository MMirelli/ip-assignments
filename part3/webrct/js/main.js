/*
 *  Copyright (c) 2015 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree.
 */

/* 
 * WebRTC overview:
 *  the protocol consists of three macro phases:
 *      1. local stream acquisition (sender webcam video);
 *      2. parameters agreement, consisting of:
 *          2.1 sender offer;
 *          2.2 receiver answer;
 *          2.3 ICE candidate.
 *      3. remote stream acquisition and data transfer (receiver gets streams).
 * 
 *      NB: 3. is automatic, once 2 is done.
 * 
 * */

'use strict';

// set this variable in order to have a larger or smaller period
// for statistics collection (playback delay and bitrate graph).
var PERIOD_STATS_S = 1;

// comment these: it's Max's stats setup
const LOCAL_STATS_NAME = 'outbound_rtp_video_0';
const REMOTE_STATS_NAME = 'inbound_rtp_video_0';

// search for field framesEncoded in logs and replace fill_here1 with the id of the Object
//const LOCAL_STATS_NAME = <fill_here1>;

// search for field framesDecoded in logs and replace fill_here2 with the id of the Object
//const REMOTE_STATS_NAME = <fill_here2>;

// Finally comment the console.log('DEBUG:'...); [find it in the file just searching DEBUG:].



//-------------------GUI elements----------------------
const startButton = document.getElementById('startButton');
const callButton = document.getElementById('callButton');
const hangupButton = document.getElementById('hangupButton');
const bandwidthSelector = document.querySelector('select#bandwidth');
const maxFramerateInput = document.querySelector('div#maxFramerate input');

const playbackSec = document.getElementById('myRst');
const receiverRstDiv = document.querySelector('div#receiverResults');
const senderRstDiv = document.querySelector('div#senderResults');

const selectedResolution = document.querySelector('p#selectedRes');
const resolutionInput = document.querySelector('select#resolution');
const resolutionInputSec = document.querySelector('section#resolutionInputSec');

const bitRateCanva = document.getElementById('canvaDiv');

bitRateCanva.hidden = true;
maxFramerateInput.onchange = updateBitRateSpan;

callButton.disabled = true;
hangupButton.disabled = true;
bandwidthSelector.disabled = true;
startButton.onclick = start;
callButton.onclick = call;
hangupButton.onclick = hangup;

const video1 = document.querySelector('video#senderVideo');

let senderNElem = document.getElementById('sender_n');
let senderNDesElem = document.getElementById('sender_n_des');
let shownRate = document.getElementById('shown_fRate');

let senderBandDes = document.getElementById('sender_band');

//---------------global vars---------------------------------
let SENDER_N;
let receiverVideos;
let senders;
let receiverCons;
// this is the offer 
const offerOptions = {
// only video for bitrate
//    offerToReceiveAudio: 1,
    offerToReceiveVideo: 1
};
const maxBandwidth = 0;
var isStarted = false;
// bitrate related
let bitrateGraph;
let bitrateSeries;
let lastResult;

// playback computation
var encodedFrames = [0,"0<br>"];
var encodedTimes = [0,"0<br>"];

var decodedFrames = [0,"0<br>"];
var decodedTimes = [0,"0<br>"];


checkBitRateStats()

//--------------setting received streams----------------------
function setUpReceiverVideos(){
    // here we setup the environment to display the videos as
    // they were sent to the receiver
    SENDER_N = Number(senderNElem.value);
    senderNElem.hidden = true;
    senderNDesElem.hidden = true;
    receiverVideos = new Array(SENDER_N);

    // the list of connections open by
    // each sender in the many-to-one case
    senders = new Array(SENDER_N);

    // list of connections open receiver-side in the
    // case many-to-one
    receiverCons = new Array(SENDER_N);

    var sib;
    var newVideo;
    // dynamic creation of the video html elements
    for ( var i=SENDER_N-1; i>=0; i--){
	sib = document.getElementById('recVideoAnchor');
	receiverVideos[i] = document.createElement("video");
	
	sib.after(receiverVideos[i]);
	receiverVideos[i].id = 'receiverVideo'.concat(i);
	receiverVideos[i].setAttribute('playsinline','');
	receiverVideos[i].setAttribute('autoplay','');
	receiverVideos[i].setAttribute('muted','');
    }
    
}

//-----------------protocol related methods-------------------
async function start() {
    // on start button pressing (protocol step 1)
    setUpReceiverVideos();
    console.log('Requesting local stream');
    startButton.disabled = true;
    isStarted = true;

    selectedResolution.hidden = false;
    const span = document.querySelector('span#selectedResValue');
    console.log(resolutionInput.value, span);
    span.textContent = resolutionInput.value;
    resolutionInputSec.hidden = true;
    
    try {
	// request for auth to access camera and audio
	var constraints = getUserMediaConstraints();
	const userMedia = await navigator.mediaDevices.getUserMedia(constraints);
	gotStream(userMedia);
	maxFramerateInput.hidden = true;
    } catch (e) {
	const message = `getUserMedia error: ${e.name}\nPermissionDeniedError may mean invalid constraints.`;
	alert(message);
	console.log(message);
	hangup();
    }
}

function gotStream(stream) {
    // on acquire local stream 
    console.log('Received local stream sender');
    video1.srcObject = stream;
    window.localStream = stream;
    callButton.disabled = false;
}

function onCreateSessionDescriptionError(error) {
    console.log('Failed to create session description: ' + error.toString());
}

function call() {
    // on call button pressing (protocol step 2)
    callButton.disabled = true;
    hangupButton.disabled = false;
    bandwidthSelector.disabled = false;
    bitRateCanva.hidden = false;
    playbackSec.hidden = false;

    bitrateSeries = new TimelineDataSeries();
    bitrateGraph = new TimelineGraphView('bitrateGraph', 'bitrateCanvas');
    bitrateGraph.updateEndDate();

    console.log('Starting calls');

    
    const audioTracks = window.localStream.getAudioTracks();
    const videoTracks = window.localStream.getVideoTracks();
    
    if (audioTracks.length > 0) {
	console.log(`Using audio device: ${audioTracks[0].label}`);
    }
    if (videoTracks.length > 0) {
	console.log(`Using video device: ${videoTracks[0].label}`);
    }
    // this loop creates the RTC connections, one per sender-receiver
    // pair, having chosen the P2P solution 
    for (var i = 0; i<SENDER_N; i++){
	const servers = null;
	// configuration set to null 
	//  (protocol step 2.1)
	senders[i] = new RTCPeerConnection(servers);
	receiverCons[i] = new RTCPeerConnection(servers);
	// tells the receiver what to do when a remote stream has been
	// received
	
	senders[i].onicecandidate =
	    // setting the ICE candidates callbacks (protocol step 2.2)
	    iceCallback1Local.bind({pc:receiverCons[i], id:i});

	receiverCons[i].onicecandidate =
	    iceCallback1Remote.bind({pc:senders[i], id:i});
	receiverCons[i].ontrack = gotRemoteStream.bind({id:i});

	console.log('pc'.concat(i).
			 concat(': connection objects created')
	);
	
	// making available video and audio tracks from localStream
	// to sender
	window.localStream.getTracks().
	       forEach(track =>
		   senders[i].addTrack(track, window.localStream)
	       );

    console.log(`Adding local stream to sender${i}`);
	// sender creates an offer (protocol step 2.1)
	senders[i]
	    .createOffer(offerOptions)
	    .then(gotDescription1Local.bind({id:i}),
		  onCreateSessionDescriptionError
	    );
    }
}

function onCreateSessionDescriptionError(error) {
    console.log(`Failed to create session description: ${error.toString()}`);
}

function onSetSessionDescriptionError(error) {
    console.log('Failed to set session description: ' + error.toString());
}

function gotDescription1Local(desc) {
    // starts offer (protocol step 2.1) and triggers an answer
    console.log(`Offer from senders${this.id}\n${desc.sdp}`);
    senders[this.id].setLocalDescription(desc).then(
	() => {
	    receiverCons[this.id].setRemoteDescription(desc)
				 .then(() => receiverCons[this.id].createAnswer()
                                 .then(gotDescription1Remote.bind({id:this.id}),
				 onCreateSessionDescriptionError),
				 onSetSessionDescriptionError);
	}, onSetSessionDescriptionError
    );
}

function gotDescription1Remote(desc) {
    // starts answer (protocol step 2.2) and triggers ICE candidates
    receiverCons[this.id].setLocalDescription(desc).then(
	() => {
	    console.log(`Answer from receiverCons${this.id}\n${desc.sdp}`);
            let p;
            if (maxBandwidth) {
		p = senders[this.id].setRemoteDescription({
		    type: desc.type,
		    sdp: updateBandwidthRestriction(desc.sdp, maxBandwidth)
		});
            } else {
		p = senders[this.id].setRemoteDescription(desc);
            }
            p.then(() => {}, onSetSessionDescriptionError);
	},
	onSetSessionDescriptionError
    );
}

function hangup() {
    // on hangup button pressing
    console.log('Ending calls');

    if (senders !== null &&
	senders[0] !== undefined &&
	receiverCons[0] !== undefined){
	for (var i = 0; i < SENDER_N; i++){
	    senders[i].close();
	    receiverCons[i].close();
	    // removes video from html
	}
    }
    for (var i = 0; i < SENDER_N; i++){
	receiverVideos[i].
		 parentNode.
		      removeChild(receiverVideos[i]);
    }
    isStarted = false;

    receiverCons = null;
    senders = null;

    hangupButton.disabled = true;
    callButton.disabled = true;
    startButton.disabled = false;

    senderNElem.hidden = false;
    senderNDesElem.hidden = false;

    maxFramerateInput.hidden = false;
    bandwidthSelector.disabled = true;
    bitRateCanva.hidden = true;

    playbackSec.hidden = true;

    selectedResolution.hidden = true;
    resolutionInputSec.hidden = false;
}

function gotRemoteStream(e) {
    // handling the remote stream
    console.log(`gotRemoteStream:`, e, receiverVideos);
    if (receiverVideos[this.id].srcObject
	!== e.streams[0]) {
	
	receiverVideos[this.id].srcObject = e.streams[0];
	
	console.log(`receiver${this.id}: received remote stream`);
    }
}

function iceCallback1Local(event) {
    // (protocol step 2.3) for senders
    if (event.candidate){
	handleCandidate(event.candidate, this.pc,
			'sender' + this.id, 'local');
    }
}

function iceCallback1Remote(event) {
    // (protocol step 2.3) for receivers
    if (event.candidate){
	handleCandidate(event.candidate, this.pc,
			'receiver' + this.id, 'remote');
    }
}

function handleCandidate(candidate, dest, prefix, type) {
    // (protocol step 2.3) 
    dest.addIceCandidate(candidate)
	.then(onAddIceCandidateSuccess,
	      onAddIceCandidateError);
    
    console.log(`${prefix}:New ${type} ICE candidate: ${candidate ? candidate.candidate : '(null)'}`);
}

function onAddIceCandidateSuccess() {
    console.log('AddIceCandidate success.');
}

function onAddIceCandidateError(error) {
    console.log(`Failed to add ICE candidate: ${error.toString()}`);
}


//-----------------stats related methods----------------------

//--------------frame rate-------------------------
function getUserMediaConstraints() {
    // set frame rate on start button pressed
    const constraints = {};
    constraints.audio = false;
    constraints.video = {};

    var selectedResolutionDim = resolutionInput.value.split('x');
    constraints.video.width = {};
    constraints.video.height = {};
    constraints.video.width.exact = selectedResolutionDim[0];
    constraints.video.height.exact = selectedResolutionDim[1];

    if (maxFramerateInput.value !== 'unlimited' &&
	maxFramerateInput.value !== '0') {
	constraints.video.frameRate = constraints.video.frameRate || {};
	constraints.video.frameRate.max = maxFramerateInput.value;
    } 
    
    return constraints;
}

function updateBitRateSpan(e){
    const span = e.target.parentElement.querySelector('span');
    if (e.target.value === '0'){
	span.textContent = 'unlimited';
    } else {
	span.textContent = e.target.value;
    }
}

//----------------playback delay--------------------
function getStat(stats, statId, key){
    var rst = '';
    stats.forEach( stat => {
	// comment line below, to have nice logs
	console.log('DEBUG:',stat);
 	if(stat['id'] === statId){
    	    Object.keys(stat).forEach(k  => {
		if (k === key) {
		    rst = `${stat[k]}<br>`;
		}
	    });
	}
    });
    return rst;
}

function concat2Times(concatMsg, data){
    var rst = concatMsg + " t0: " + data[0];
    rst += concatMsg + " t1: " + data[1];
    return rst;
}

function getLocalStats(stats){
    var rst = "Delay sender<br>";
    
    var framesMsg = 'framesEncoded';
    var tsMsg = 'encodingTimestamp';
    
    encodedFrames[0] = encodedFrames[1];
    
    encodedFrames[1] = getStat(stats, LOCAL_STATS_NAME, 'framesEncoded');
    rst += concat2Times(framesMsg, encodedFrames);
    
    encodedTimes[0] = encodedTimes[1];
    encodedTimes[1] = getStat(stats, LOCAL_STATS_NAME, 'timestamp');
    rst += concat2Times(tsMsg, encodedTimes);
    
    senderRstDiv.innerHTML = `${rst}`;
}

function getRemoteStats(stats){  
    var rst = "Delay receiver<br>";
    
    var framesMsg = 'framesDecoded';
    var tsMsg = 'decodingTimestamp';
    
    decodedFrames[0] = decodedFrames[1];
    decodedFrames[1] = getStat(stats, REMOTE_STATS_NAME, 'framesDecoded');
    rst += concat2Times(framesMsg, decodedFrames);
    
    decodedTimes[0] = decodedTimes[1];
    decodedTimes[1] = getStat(stats, REMOTE_STATS_NAME, 'timestamp');
    rst += concat2Times(tsMsg, decodedTimes);
    
    console.log(rst);
    receiverRstDiv.innerHTML = `${rst}`;
}

//--------------bit rate-----------------------
// renegotiate bandwidth on the fly.
bandwidthSelector.onchange = () => {
    bandwidthSelector.disabled = true;
    const bandwidth = bandwidthSelector.options[bandwidthSelector.selectedIndex].value;

    var sender;
    var parameters;
    for (var i=0; i<SENDER_N; i++){
	console.log("Changing bitrate to ", bandwidth);
	// In Chrome, use RTCRtpSender.setParameters to change bandwidth without
	// (local) renegotiation. Note that this will be within the envelope of
	// the initial maximum bandwidth negotiated via SDP.
	if ((adapter.browserDetails.browser === 'chrome' ||
	     (adapter.browserDetails.browser === 'firefox' &&
              adapter.browserDetails.version >= 64)) &&
	    'RTCRtpSender' in window &&
	    'setParameters' in window.RTCRtpSender.prototype) {
	    sender = senders[i].getSenders()[0];
	    
	    parameters = sender.getParameters();
	    if (!parameters.encodings) {
		parameters.encodings = [{}];
	    }
	    if (bandwidth === 'unlimited') {
		delete parameters.encodings[0].maxBitrate;
	    } else {
		parameters.encodings[0].maxBitrate = bandwidth * 1000;
	    }

	    sender.setParameters(parameters)
		  .then(() => {
		      bandwidthSelector.disabled = false;
		  })
		  .catch(e => console.error(e));
	}
    }
};

function updateBandwidthRestriction(sdp, bandwidth) {
    let modifier = 'AS';
    if (adapter.browserDetails.browser === 'firefox') {
	bandwidth = (bandwidth >>> 0) * 1000;
	modifier = 'TIAS';
    }
    if (sdp.indexOf('b=' + modifier + ':') === -1) {
	// insert b= after c= line.
	sdp = sdp.replace(/c=IN (.*)\r\n/, 'c=IN $1\r\nb=' + modifier + ':' + bandwidth + '\r\n');
    } else {
	sdp = sdp.replace(new RegExp('b=' + modifier + ':.*\r\n'), 'b=' + modifier + ':' + bandwidth + '\r\n');
    }
    return sdp;
}

function removeBandwidthRestriction(sdp) {
    return sdp.replace(/b=AS:.*\r\n/, '').replace(/b=TIAS:.*\r\n/, '');
}

function sleep (time) {
    return new Promise((resolve) => setTimeout(resolve, time));
}


//----------------------update stats-----------------------
// sleep 5 secs and start gathering bitrate stats
function checkBitRateStats() {
    
    if (!isStarted) {
        setTimeout(checkBitRateStats, 2000); // setTimeout(func, timeMS, params...)
    } else {
	computeBitRateStats();
    }
}

function computeBitRateStats(){
    // query getStats every second
    window.setInterval(() => {
	//----------playback delay stats-----------------------
	if (!senders || !senders[0]) {
	    return;
	}
	else {
	    receiverCons[0].getStats(null)
		.then(getRemoteStats, err => console.log(err));

	    senders[0].getStats(null)
		.then(getLocalStats, err => console.log(err));
	} 

	//-----------bit rate stats---------------------------
	const sender = senders[0].getSenders()[0];
	if (!sender) {
	    return;
	}
	sender.getStats().then(res => {
	    res.forEach(report => {
		let bytes;
		let packets;
		if (report.type === 'outbound-rtp') {
		    if (report.isRemote) {
			return;
		    }
		    const now = report.timestamp;
		    bytes = report.bytesSent;
		    packets = report.packetsSent;
		    if (lastResult && lastResult.has(report.id)) {
			// calculate bitrate
			const bitrate = 8 * (bytes - lastResult.get(report.id).bytesSent) /
			(now - lastResult.get(report.id).timestamp);
			console.log('Bitrate ', bitrate, ' kbps');

			// append to chart
			bitrateSeries.addPoint(now, bitrate);
			bitrateGraph.setDataSeries([bitrateSeries]);
			bitrateGraph.updateEndDate();

			// calculate number of packets and append to chart
		    }
		}
	    });
	    lastResult = res;
	});
    }, PERIOD_STATS_S * 1000);
}

setInterval(() => {
}, 1000);
