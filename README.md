# Sipwise rtpengine speech to text via Google Speech API

This is a proof of concept to utilize Sipwise rtpengine and its rtp fan-out /proc interface to
transcribe an ongoing call from speech to text in near real time using the Google Speech API.

## Prerequisites

Obtain a google-service-account.json file using the google compute cli tools according to the API
documentation provided by Google API documentation.

## Install

Copy scripts to an NGCP (e.g. a Sipwise CE installation), enable call recording on the system,
start the tools and place a call.
