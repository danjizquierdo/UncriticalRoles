import tweepy
import json
import config
from datetime import date, timedelta
import re
import logging
from sys import argv
import string
import re
import nltk
from nltk import word_tokenize, FreqDist
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import string
from wordcloud import WordCloud
from PIL import Image
import matplotlib.pyplot as plt
from collections import Counter
import numpy as np
import urllib
import requests
import jsonlines


logging.basicConfig(filename='errors.log', filemode='a+', format='%(asctime)s: %(message)s', level=logging.ERROR)

auth = tweepy.OAuthHandler(config.consumer_key, config.consumer_secret)
auth.set_access_token(config.access_token, config.access_token_secret)
api = tweepy.API(auth, wait_on_rate_limit=True)

nltk.download('wordnet')

mask = np.array(Image.open(requests.get('https://www.laserlogik.com/wp-content/uploads/2018/03/map-RED-Iowa-1.png',
                                        stream=True).raw))
lemmatizer = WordNetLemmatizer()


def process_tweet(tweet):
    """ Takes in a string, returns a list words in the string that aren't stopwords
    Parameters:
        tweet (string):  string of text to be tokenized
    Returns:
        stopwords_removed (list): list of all words in tweet, not including stopwords
    """
    stopwords_list = stopwords.words('english')
    stopwords_list += ["'",'"','...','``','…','’','‘','“',"''",'""','”','”','co',
                       "'s'",'\'s','n\'t','\'m','\'re','amp','https']
    tokens = nltk.word_tokenize(tweet.translate(str.maketrans(dict.fromkeys(string.punctuation))))
    stopwords_removed = [lemmatizer.lemmatize(token).lower() for token in tokens if token not in stopwords_list]
    return stopwords_removed


def tokenized(series):
    """ Takes in a series containing strings or lists of strings, and creates a single list of all the words
    Parameters:
        series (series): series of text in the form of strings or lists of string

    Returns:
        tokens (list): list of every word in the series, not including stopwords
    """

    corpus = ' '.join(
        [tweet.lower() if type(tweet) == str else ' '.join([tag.lower() for tag in tweet]) for tweet in series])
    tokens = process_tweet(corpus)
    return tokens


def wordfrequency(series, top):
    """ Returns the frequency of words in a list of strings.
    Parameters:
        series (iterable): List of strings to be combined and analyzed
        top (int): The number of top words to return.
    Returns:
        list (tuples): List of word and value pairs for the top words in the series.
    """
    frequencies = FreqDist(tokenized(series))
    return frequencies.most_common(top)


def create_wordcloud(series, tag, *top):
    """ Take in a list of lists and create a WordCloud visualization for those terms.
    Parameters:
            series (iterable): A list of lists containing strings.
    Returns:
        None: The ouput is a visualization of the strings in series in terms of the
            frequency of their occurrence.
    """

    vocab = tokenized(series)
    if not top[0]:
        top[0] = 200
    cloud = WordCloud(background_color='grey', max_words=top[0], mask=mask).generate(' '.join([word for word in vocab]))
    plt.imshow(cloud, interpolation='bilinear')
    plt.title(f'Most Common words for {tag}')
    plt.plot(figsize = (48,24))
    plt.axis('off')
    plt.show();

def strip_tweets(tweet):
    """ Process tweet text to remove retweets, mentions,links and hashtags. """
    retweet = r'RT:? ?@\w+:?'
    tweet = re.sub(retweet, '', tweet)
    mention = r'@\w+'
    tweet = re.sub(mention, '', tweet)
    links = r'^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$'
    tweet = re.sub(links, '', tweet)
    tweet_links = r'https:\/\/t\.co\/\w+|http:\/\/t\.co\/\w+'
    tweet = re.sub(tweet_links, '', tweet)
    tweet_link = r'http\S+'
    tweet = re.sub(tweet_link, '', tweet)
    hashtag = r'#\w+'
    hashtags = re.findall(hashtag, tweet)
    tweet = re.sub(hashtag, '', tweet)
    return tweet, hashtags


def cluster_flocks(dicts):
    hashtags = Counter()
    tweets = []
    for dic in dicts.values():
        text, tag = strip_tweets(dic['text'])
        hashtags.update(tag)
        tweets.append([text, tag])
    return tweets, hashtags


def myconverter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()


def listen(terms, amount):
    today = date.today()
    last_week = today - timedelta(days=7)
    for term in terms:
        for tweet in tweepy.Cursor(api.search, q=term, count=amount, lang='en',
                                   tweet_mode='extended', since=last_week.isoformat()).items(amount):
            if (not tweet.retweeted) and ('RT @' not in tweet.full_text):
                user_ = dict()
                tweet_ = dict()
                try:
                    user_['screen_name'] = tweet.user.screen_name
                    user_['verified'] = tweet.user.verified
                    user_['id'] = tweet.user.id
                    if tweet.user.lang:
                        user_['lang'] = tweet.user.lang
                    tweet_['user'] = user_
                except Exception as e:
                    print(e)
                    logging.error(f'Error on status_to_dict[User]: {e}\nFailed tweet: {tweet._json}\n')
                    tweet_['user'] = None
                else:
                    with jsonlines.open(f'{today.isoformat()}-users.json',
                                        mode='a') as writer:
                        writer.write(user_)
                try:
                    tweet_ = dict()
                    tweet_['timestamp'] = tweet.created_at.timestamp()
                    if 'extended_text' in tweet._json.keys():
                        tweet_['text'] = tweet.extended_text.full_text
                    else:
                        tweet_['text'] = tweet.full_text
                    tweet_['user_id'] = tweet.user.id
                    tweet_['coordinates'] = tweet.coordinates
                    tweet_['id'] = int(tweet.id)
                except Exception as e:
                    print(e)
                    logging.error(f'Error on status_to_dict[Tweet]: {e}\nFailed tweet: {tweet._json}\n')
                else:
                    with jsonlines.open(f'{today.isoformat()}-tweets.json',
                                        mode='a') as writer:
                        writer.write(tweet_)
        print(f'Done listening for {term}!')




if __name__ == "__main__":
    if len(argv)>1:
        topics = argv[1:]
    else:
        topics = [
            '@WillingBlam', '@Marisha_Ray', '@TheVulcanSalute', '@MatthewMercer', '@samriegel',
            '@LaureyBaileyVO', '@VoiceOfBrien', '@executivegoth', '@ItsDaniCarr', '@BrianWFoster',
            '@criticalrole', '#criticalrole', '#critters', '@TalksMachina'
        ]
    listen([str(topic) for topic in topics], 1000)
