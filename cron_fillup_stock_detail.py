# %%
import requests
import pymongo

# %%
MAX_COMMENT = 15    #each stock should have max 20 comments
MAX_REPLY = 5   #each comment should have max 6 comments
MAX_LIKE = 50   #each comment or like should have max 50 likes
MIN_COMMENT_TIMESTAMP = 1705571059  #sec (18 Jan 2024)

# %%
from dotenv import load_dotenv
load_dotenv() 
import os

FINNHUB_KEY = os.environ['FINNHUB_KEY']
FINNHUB_URI = os.environ['FINNHUB_URI']
GG_GEMINI_API = os.environ['GG_GEMINI_API']

# %% [markdown]
# 1. Get 1 stock from db which there is no name
# 2. Get basic detail of that stock
# 3. Generate 10 - 20 random comments for that stock, with random like number
# 4. Generate random 0 - 8 replies for each comment, with random like number
# 5. Save comments and likes into db

# %%
db_client = pymongo.MongoClient('mongodb://localhost:27017')
collections = db_client['stock_forum']
tbl_stock = collections['tbl_stock']
tbl_user = collections['tbl_user']
tbl_comment = collections['tbl_comment']
tbl_reply = collections['tbl_reply']

# %%
db_stock = tbl_stock.find_one({'name': None})

symbol = ''
if db_stock is not None:
    symbol = db_stock['symbol']
    print('symbol: ' + symbol)

# %%
#query data from Finnhub but limit 30 APIs/second
#https://finnhub.io/docs/api/stock-symbols
def custom_query(get_url):
    #print(get_url)
    try:
        r = requests.get(get_url)
        return r.json()
    except Exception as e:
       print(e)
       return r

# %%
import random

def get_random_like():
    return random.randint(0, MAX_LIKE)

# %%
def get_random_number(max_num):
    return random.randint(1, max_num)

# %%
import re
import json

def extract_json(text_response):
    # This pattern matches a string that starts with '{' and ends with '}'
    pattern = r'\{[^{}]*\}'
    matches = re.finditer(pattern, text_response)
    json_objects = []
    for match in matches:
        json_str = match.group(0)
        try:
            # Validate if the extracted string is valid JSON
            json_obj = json.loads(json_str)
            json_objects.append(json_obj)
        except json.JSONDecodeError:
            # Extend the search for nested structures
            extended_json_str = extend_search(text_response, match.span())
            try:
                json_obj = json.loads(extended_json_str)
                json_objects.append(json_obj)
            except json.JSONDecodeError:
                # Handle cases where the extraction is not valid JSON
                continue
    if json_objects:
        return json_objects
    else:
        return None  # Or handle this case as you prefer
    
def extend_search(text, span):
    # Extend the search to try to capture nested structures
    start, end = span
    nest_count = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            nest_count += 1
        elif text[i] == '}':
            nest_count -= 1
            if nest_count == 0:
                return text[start:i+1]
    return text[start:end]

# %%
#Send a POST request
def post_request_gemini(text_prompt):
    gemini_url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key='+GG_GEMINI_API
    HEADER = {'Content-Type': 'application/json'}
    json_data = {
        "contents": [
            { "parts": [
                {"text": text_prompt + " Please provide a response in a structured JSON format."}]
            }
        ]
    }

    try:
        r = requests.post(gemini_url, headers=HEADER, json=json_data)
        return r.json()
    except Exception as e:
       print(e)
       return e

# %%
def get_rand_comments():
    comment_num = get_random_number(MAX_COMMENT)
    #generate random posts for each stock
    fake_comments = post_request_gemini('Generate '+str(comment_num)+' random comments for this stock symbol ' + symbol +" natually as human saying. Each setence should have 30 to 50 words length.") #10 sec
    # print(fake_comments)
    raw_comments = fake_comments['candidates'][0]['content']['parts'][0]['text']
    #extract json structure
    json_comments = extract_json(raw_comments)
    return json_comments

# %%
def get_rand_relies(str_comment):
    reply_num = get_random_number(MAX_REPLY)
    reply_list = []
    #generate random relies for the comment
    fake_replies = post_request_gemini('Generate '+str(reply_num)+' random replies for the comment: ' + str_comment +' of this stock symbol '+symbol+' natually as human saying. Each reply should have 10 to 20 words length.') #10 sec
    if 'candidates' in fake_replies:
        raw_replies = fake_replies['candidates'][0]['content']['parts'][0]['text']
        #extract json structure
        json_replies = extract_json(raw_replies)
        for reply in json_replies:
            if 'text' in reply:
                reply_list.append(reply['text'])
    return reply_list

# %%
import uuid
def generate_random_uuid():
    return str(uuid.uuid4())

# %%
import random
import time

def get_random_timestamp(start_time):
    current_time = int(time.time())
    time_delta = current_time - start_time
    random_offset = random.randint(0, time_delta)
    random_timestamp = start_time + random_offset
    return random_timestamp

# %%
def insert_comment(str_comment):
    #print(str_comment)
    #get random user
    random_name = tbl_user.aggregate([{"$sample": {"size": 1}}]).next()
    username = random_name['usr']
    #generate random ID
    comment_uuid = generate_random_uuid()
    #generate random likes
    cmt_like = get_random_like()
    #generate random timestamp
    rand_time = get_random_timestamp(MIN_COMMENT_TIMESTAMP)
    #insert this comment to db
    comment_detail = {
        'symbol': symbol,
        'uuid': comment_uuid,
        'usr': username,
        'like': cmt_like,
        'time': rand_time,
        'text': str_comment.replace('  ', ' ')
    }
    tbl_comment.insert_one(comment_detail)
    return comment_detail

# %%
def insert_reply(str_reply, comment_detail):
    #get random user
    random_name = tbl_user.aggregate([{"$sample": {"size": 1}}]).next()
    username = random_name['usr']
    #generate random ID
    reply_uuid = generate_random_uuid()
    #generate random likes
    reply_like = get_random_like()
    #generate random timestamp
    rand_time = get_random_timestamp(comment_detail['time'])
    #insert this reply to db
    reply_detail = {
        'uuid': reply_uuid,
        'cmt_uuid': comment_detail['uuid'],
        'usr': username,
        'like': reply_like,
        'time': rand_time,
        'text': str_reply.replace('  ', ' ')
    }
    tbl_reply.insert_one(reply_detail)
    return reply_detail

# %%
if symbol != '':
    #1. Get stock detail
    stock_detail_url = FINNHUB_URI + 'stock/profile2?symbol='+symbol+'&token=' + FINNHUB_KEY
    stock_detail = custom_query(stock_detail_url)
    #print(stock_detail)
    if stock_detail is not None and 'name' in stock_detail:
        #generate and save comments
        comment_list = get_rand_comments()
        # print(comment_list)
        if len(comment_list) > 0:
            #take each comment
            for json_comment in comment_list:
                #save comment to db
                comment_detail = insert_comment(json_comment['comment'])
                reply_list = get_rand_relies(json_comment['comment'])
                #print(reply_list)
                if len(reply_list) > 0:
                    for str_reply in reply_list:
                        insert_reply(str_reply, comment_detail)
        #update stock info to db
        tbl_stock.update_one({'symbol': symbol}, {'$set':{
                'name': stock_detail['name'],
                'industry': stock_detail['finnhubIndustry'],
                'ipo': stock_detail['ipo'],
                'cap': stock_detail['marketCapitalization'],
                'web': stock_detail['weburl']
            }})
    else:
        #somehow cannot get detail of this stock, mark it to process later
        tbl_stock.update_one({'symbol': symbol}, {'$set':{
                "name" : "no_detail"
            }})
    print('Finish symbol ' + symbol)


# %%



