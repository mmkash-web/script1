#!/usr/bin/env python3
import csv
import logging
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger()

URL = 'https://cdk.goatspins.com:3072/lobby/'
