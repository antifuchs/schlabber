#!/usr/bin/env python3
import os
import stat
import argparse
import datetime
import requests
import json
import pprint
import hashlib
import time
from http.cookiejar import CookieJar
from bs4 import BeautifulSoup

class Soup:
    def assertdir(self,dirname):
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

    def __init__(self, soup, bup_dir):
        self.rooturl = "https://"+soup+".soup.io"
        self.bup_dir = os.path.abspath(bup_dir)
        self.assertdir(self.bup_dir)
        self.dlnextfound = False
        self.sep = os.path.sep
        print("Backup: " + self.rooturl)
        print("into: " + self.bup_dir)

    def find_next_page(self, cur_page):
        for script in cur_page.find_all('script'):
            if script.string and "SOUP.Endless.next_url" in script.string:
                print("\t...found")
                self.dlnextfound = True
                nexturl = script.string.split('\'')[-2].strip()
                if nexturl != "none":
                    return nexturl
        self.dlnextfound = False
        return ""

    def get_asset_filename(self, name):
        return name.split('/')[-1]

    def get_timestamp(self, post):
        for time_meta in post.select("span.time>abbr"):
            ts = time_meta.get('title')
            return datetime.datetime.strptime(ts, '%b %d %Y %H:%M:%S %Z')
        return None

    def write_meta(self, meta, timestamp):
        year = 'unknown'
        timestr = ''
        if timestamp:
            year = timestamp.date().year
            timestr = timestamp.isoformat() + '-'
        basepath = self.bup_dir + self.sep + "posts" + self.sep + str(year) + self.sep
        self.assertdir(basepath)
        filename = basepath + timestr + meta['type'] + '-' + meta['id'] + ".json"
        if os.path.isfile(filename):
            # skip, it exists:
            return
        with open(filename, 'w') as outfile:
            json.dump(meta, outfile)

    def process_assets(self, meta, post):
        assets = []
        for link in post.find_all('div', {"class":"imagecontainer"}):
            lightbox = link.find("a", {"class": "lightbox"})
            url = None
            if lightbox:
                url = lightbox.get('href')
            else:
                url = link.find("img").get('src')
            if url is not None:
                filename = self.get_asset_filename(url)
                basepath = self.bup_dir + self.sep + 'assets' + self.sep
                path = basepath + filename
                if os.path.isfile(path) == True:
                    print("\t\t\tSkip asset " + url + ": File exists")
                else:
                    print("\t\t\tAsset URL: " + url + " -> " + path)
                    self.assertdir(basepath)
                    r = requests.get(url, allow_redirects=True)
                    with open(path, "wb") as tf:
                        tf.write(r.content)
                assets.append({'url': url, 'filename': filename})
        meta['assets'] = assets

    def process_image(self, post):
        meta = {}
        for link in post.select(".imagecontainer>.caption>a"):
            meta['source'] = link.get("href")
        for desc in post.find_all("div", {'class': 'description'}):
            meta['description'] = str(desc)
        return meta

    def process_quote(self, post):
        meta = {}
        meta['quote'] = str(post.find("span", {"class", 'body'}))
        meta['attribution'] = str(post.find("cite"))
        return meta

    def process_link(self, post):
        meta = {}
        linkelem = post.find("h3")
        meta["link_title"] = str(linkelem)
        meta["url"] = linkelem.find('a').get('href')
        meta["body"] = str(post.find('span', {'class','body'}))
        return meta

    def process_video(self, post):
        meta = {}
        meta['embed'] = str(post.find("div", {'class':'embed'}))
        source = post.select("div.admin-edit textarea.sourcecode")
        if len(source) == 1:
            # for soups on which we can edit, fetch the source:
            meta['source'] = source[0].text.strip()
        bodyelem = post.find("div", {'class':'body'})
        if bodyelem:
            meta['body'] = str(bodyelem)
        return meta

    def process_file(self, post):
        meta = {}
        linkelem = post.find("h3")
        if linkelem:
            meta["link_title"] = str(linkelem)
            meta["url"] = linkelem.find('a').get('href')
        meta["body"] = str(post.find('div', {'class','body'}))
        return meta

    def process_review(self, post):
        meta = {}
        embed = post.find("div", {'class':'embed'})
        if embed:
            meta['embed'] = str(embed)
        descelem = post.find("div", {'class','description'})
        if descelem:
            meta['description'] = str(descelem)
        meta['rating'] = post.find("abbr", {"class", "rating"}).get("title")
        h3elem = post.find("a", {"class":"url"})
        meta['url'] = h3elem.get("href")
        meta['title'] = str(h3elem)
        return meta

    def process_event(self, post):
        meta = {}
        h3elem = post.find("a", {"class":"url"})
        meta['url'] = h3elem.get("href")
        meta['title'] = str(h3elem)
        meta['date_start'] = post.find("abbr", {'class':'dtstart'}).get("title")
        dtelem = post.find("abbr", {'class':'dtend'})
        if dtelem:
            meta['date_end'] = dtelem.get("title")
        meta['location'] = str(post.find("span", {'class':'location'}))
        meta['ical_url'] = str(post.find("div", {'class': 'info'}).find('a').get('href'))
        i = requests.get(meta['ical_url'], allow_redirects=True)
        meta['ical_xml'] = str(i.content)
        descelem = post.find("div", {'class','description'})
        if descelem:
            meta['description'] = str(descelem)
        return meta

    def process_regular(self, post):
        meta = {}
        h3elem = post.find("h3")
        content = {}
        if h3elem:
            meta['title'] = str(h3elem)
        body = post.find("div", {'class':'body'})
        meta['body'] = str(body)
        return meta

    def process_unkown(self, post, post_type):
        print("\t\tUnsuported type:")
        print("\t\t\tType: " + post_type)
        meta = {}
        meta['unsupported'] = True
        return meta

    def get_meta(self, post):
        meta = {}
        if post.select('div.meta') == []:
            # We're not a real post (probably just a post-like div
            # inside a real post), quit while we're ahead.
            return None

        css_type = post.get('class')[1]
        meta['css_type'] = css_type
        meta['type'] = css_type.replace("post_", "")
        timestamp = self.get_timestamp(post)
        if timestamp:
            meta['time'] = timestamp.isoformat()
        meta['id'] = post['id']
        meta['nsfw'] = 'f_nsfw' in post.get('class')

        # permalink:
        permalink = post.select('.meta .icon.type a')[0]
        meta['permalink'] = permalink['href']

        # author:
        author = post.select('.meta div.author .user_container')[0]
        author_id = [id for id in author.get('class') if id != 'user_container'][0]
        meta['author_id'] = author_id
        meta['author_url'] = author.select('a.url')[0]['href']

        # tags:
        tags = []
        for tag_link in post.select('.content-container>.content>.tags>a'):
            tag = {"link": tag_link['href'], "name": tag_link.text}
            tags.append(tag)
        meta['tags'] = tags
        return meta


    def process_posts(self, cur_page):
        posts = cur_page.select('div.post')
        for post in posts:
            meta = self.get_meta(post)
            if meta is None:
                # We found a non-post div.
                continue
            timestamp = self.get_timestamp(post)
            meta['raw'] = str(post)
            post_type = meta['type']
            print("\t\t%s: %s %s" % (timestamp, post_type, meta['permalink']))

            if post_type == "image":
                meta['post'] = self.process_image(post)
            elif post_type == "quote":
                meta['post'] = self.process_quote(post)
            elif post_type == "video":
                meta['post'] = self.process_video(post)
            elif post_type == "link":
                meta['post'] = self.process_link(post)
            elif post_type == "file":
                meta['post'] = self.process_file(post)
            elif post_type == "review":
                meta['post'] = self.process_review(post)
            elif post_type == "event":
                meta['post'] = self.process_event(post)
            elif post_type == "regular":
                meta['post'] = self.process_regular(post)
            else:
                meta['post'] = self.process_unkown(post, post_type)

            self.process_assets(meta, post)
            self.write_meta(meta, timestamp)

    def backoff(self, message, times):
        backoff_secs = 5
        print("%s, backing off %ds..." % (message, times*backoff_secs))
        time.sleep(backoff_secs * times)
        return times + 1

    def backup(self, cont_id = None, session_cookie = None):
        dlurl = self.rooturl
        cookies={}
        if session_cookie is not None:
            cookies["soup_session_id"] = session_cookie
        if cont_id != "":
            # normalize the ID:
            cont_id = cont_id.replace("/since/", "")
            cont_id = cont_id.replace("post", "")
            dlurl += "/since/" + cont_id
        backoff_factor = 1

        while True:
            print("Get: " + dlurl)
            dl = requests.get(dlurl, cookies=cookies)
            if dl.status_code == 200:
                backoff_factor = 1
                page = BeautifulSoup(dl.content, 'html.parser')
                print("Looking for next Page")
                next = self.find_next_page(page)
                if next is None and self.dlnextfound:
                    backoff_factor = self.backoff("Could not find 'next' endless-scrolling link", backoff_factor)
                    continue
                print("Process Posts")
                self.process_posts(page)
                if self.dlnextfound == False:
                    print("no next found.")
                    break
                dlurl = self.rooturl + next
                print("Next batch of posts: " + dlurl)
            if dl.status_code == 429:
                backoff_factor = self.backoff("Rate-limited", backoff_factor)
            elif dl.status_code == 404:
                print("Page not found")
                return
            elif dl.status_code > 400: # includes 5xx status codes
                backoff_factor = self.backoff("Received %d status code" % dl.status_code, backoff_factor)

def main(soups, bup_dir, cont_from, session_cookie):
    for site in soups:
        soup = Soup(site, bup_dir)
        soup.backup(cont_from, session_cookie)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Soup.io backup')
    parser.add_argument('soups', nargs=1, type=str, default=None, help="Name your soup")
    parser.add_argument('-d','--dir', default=os.getcwd(), help="Directory for Backup (default: Working dir)")
    parser.add_argument('-c', '--continue_from', default="", help='Continue from given suburl (Example: /since/696270106?mode=own)')
    parser.add_argument('-s', '--session_cookie', default=None, help="Use this session cookie to make HTTP requests (to fetch logged-in content & see video embeds' sources)")
    args = parser.parse_args()
    main(args.soups, args.dir, args.continue_from, args.session_cookie)
