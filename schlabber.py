#!/usr/bin/env python3
import os
import stat
import argparse
import datetime
import requests
import json
import pprint
import hashlib
from bs4 import BeautifulSoup

class Soup:
    def assertdir(self,dirname):
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

    def __init__(self, soup, bup_dir):
        self.rooturl = "http://"+soup+".soup.io"
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
                return script.string.split('\'')[-2].strip()
        self.dlnextfound = False
        return ""

    def get_asset_filename(self, name):
        return name.split('/')[-1]

    def get_timestamp(self, post):
        for time_meta in post.find_all("abbr"):
            ts = time_meta.get('title')
            return datetime.datetime.strptime(ts, '%b %d %Y %H:%M:%S %Z')
        return None

    def write_meta(self, meta, timestamp):
        year = 'unknown'
        timestr = 'unknown'
        if timestamp:
            year = timestamp.date().year
            timestr = timestamp.isoformat()
        basepath = self.bup_dir + self.sep + "posts" + self.sep + str(year) + self.sep
        self.assertdir(basepath)
        filename = basepath + timestr + "-" + meta['type'] + '-' + meta['id'] + ".json"
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
        for caption in post.find_all("div", {'class': 'caption'}):
            meta['source'] = caption.find('a').get("href")
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
        for link in post.find_all('div', {"class":"imagecontainer"}):
            lightbox = link.find("a", {"class": "lightbox"})
            if lightbox:
                meta['soup_url'] = lightbox.get('href')
            else:
                meta['soup_url'] = link.find("img").get('src')
        h3elem = post.find("a", {"class":"url"})
        meta['url'] = h3elem.get("href")
        meta['title'] = str(h3elem)
        meta['date_start'] = post.find("abbr", {'class':'dtstart'}).get("title")
        dtelem = post.find("abbr", {'class':'dtend'})
        if dtelem:
            meta['date_end'] = dtelem.get("title")
        meta['location'] = post.find("span", {'class':'location'})
        meta['ical_url'] = post.find("div", {'class': 'info'}).find('a').get('href')
        i = requests.get(meta['ical_url'], allow_redirects=True)
        meta['ical_xml'] = i.content
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
        print("\t\tUnsuported tpye:")
        print("\t\t\tType: " + post_type)
        meta = {}
        meta['unsupported'] = True
        return meta

    def get_meta(self, post):
        meta = {}
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
        posts = cur_page.find_all('div', {"class": "post"})
        for post in posts:
            post_type = post.get('class')[1]
            timestamp = self.get_timestamp(post)
            meta = self.get_meta(post)
            meta['raw'] = str(post)
            print("\t\t%s: %s %s" % (timestamp, post_type, meta['id']))

            if post_type == "post_image":
                meta['post'] = self.process_image(post)
            elif post_type == "post_quote":
                meta['post'] = self.process_quote(post)
            elif post_type == "post_video":
                meta['post'] = self.process_video(post)
            elif post_type == "post_link":
                meta['post'] = self.process_link(post)
            elif post_type == "post_file":
                meta['post'] = self.process_file(post)
            elif post_type == "post_review":
                meta['post'] = self.process_review(post)
            elif post_type == "post_event":
                meta['post'] = self.process_event(post)
            elif post_type == "post_regular":
                meta['post'] = self.process_regular(post)
            else:
                meta['post'] = self.process_unkown(post, post_type)

            self.process_assets(meta, post)
            self.write_meta(meta, timestamp)


    def backup(self, cont_id = None):
        dlurl = self.rooturl
        if cont_id != "":
            # normalize the ID:
            cont_id = cont_id.replace("/since/", "")
            cont_id = cont_id.replace("post", "")
            dlurl += "/since/" + cont_id

        while True:
            print("Get: " + dlurl)
            dl = requests.get(dlurl)
            if dl.status_code == 200:
                page = BeautifulSoup(dl.content, 'html.parser')
                print("Looking for next Page")
                dlurl = self.rooturl + self.find_next_page(page)
                print("Process Posts")
                self.process_posts(page)
                if self.dlnextfound == False:
                    print("no next found.")
                    break
            elif dl.status_code > 500:
                print("Received 500 status, backing off...")
                sleep(5)
            elif dl.status_code > 400:
                print("Page not found")
                return

def main(soups, bup_dir, cont_from):
    for site in soups:
        soup = Soup(site, bup_dir)
        soup.backup(cont_from)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Soup.io backup')
    parser.add_argument('soups', nargs=1, type=str, default=None, help="Name your soup")
    parser.add_argument('-d','--dir', default=os.getcwd(), help="Directory for Backup (default: Working dir)")
    parser.add_argument('-c', '--continue_from', default="", help='Continue from given suburl (Example: /since/696270106?mode=own)')
    args = parser.parse_args()
    main(args.soups, args.dir, args.continue_from)
