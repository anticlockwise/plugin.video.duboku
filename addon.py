# -*- coding: utf-8 -*-

from kodiswift import Plugin, xbmcplugin
import requests
import bs4
import re
import string


DUBOKU_URL = "https://duboku.co"
URL_REGEX = re.compile(
    r"url\":\"https:\\/\\/(\w+\.\w+\.com)\\/(\d+)\\/([a-zA-Z0-9]+)\\/index\.m3u8")
EPISODE_EXTRACTOR = re.compile(r"\d+")
SEASON_YEAR_EXTRACTOR = re.compile(r"[12][0-9][0-9][0-9]$")
SEASON_CHN_EXTRACTOR = re.compile(r"第(\w+?)季".decode("utf-8"), re.UNICODE)
CHINESE_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
CHINESE_NUMBERS_DICT = {num.decode("utf-8"): str(i + 1)
                        for i, num in enumerate(CHINESE_NUMBERS)}
RATING_EXTRACTOR = re.compile(r"1?[0-9]\.[0-9]")
PATH_PARTS_EXTRACTOR = re.compile(
    r"(?P<base_path>\d+--(time|hits))------(?P<page_num>[0-9]?)---")


plugin = Plugin()


def _get_html(path):
    res = requests.get(path)
    html = res.text
    return bs4.BeautifulSoup(html, features="html.parser")


def _get_season_number(text):
    season_year = SEASON_YEAR_EXTRACTOR.search(text)
    if season_year:
        return season_year.group(0)
    season_chn_text_match = SEASON_CHN_EXTRACTOR.search(text)
    if season_chn_text_match:
        season_chn_text = season_chn_text_match.group(1)
        season_number = CHINESE_NUMBERS_DICT.get(season_chn_text)
        if not season_number and season_chn_text.isnumeric():
            season_number = season_chn_text
        if len(season_number) < 2:
            season_number = "0{}".format(season_number)
        return season_number
    return "01"


@plugin.route('/')
def index():
    categories = [{
        "label": "综艺".decode("utf-8"),
        "path": plugin.url_for('show_category', path="vodshow", category="3--time---------.html")
    }, {
        "label": "连续剧 - 时间".decode("utf-8"),
        "path": plugin.url_for('show_category', path="vodshow", category="2--time---------.html")
    }, {
        "label": "连续剧 - 人气".decode("utf-8"),
        "path": plugin.url_for('show_category', path="vodshow", category="2--hits---------.html")
    }]
    return categories


@plugin.route("/categories/<path>/<category>/")
def show_category(path, category):
    soup = _get_html(DUBOKU_URL + "/" + path + "/" + category)
    shows_elems = soup.select(".myui-panel-bg .myui-vodlist__box")
    shows = []

    path_parts_match = PATH_PARTS_EXTRACTOR.search(category)
    if path_parts_match:
        base_path = path_parts_match.group("base_path")
        page_num = path_parts_match.group("page_num")
        if page_num == "":
            page_num = "1"
        next_page_num = int(page_num) + 1
        next_page_url = "{}------{}---.html".format(base_path, next_page_num)
        shows.append({
            "label": "下一页",
            "path": plugin.url_for("show_category", path="vodshow", category=next_page_url)
        })

        if next_page_num > 2:
            prev_page_num = int(page_num) - 1
            prev_page_url = "{}------{}---.html".format(
                base_path, prev_page_num)
            shows.append({
                "label": "上一页",
                "path": plugin.url_for("show_category", path="vodshow", category=prev_page_url)
            })

    for show in shows_elems:
        link = show.find("a")
        rating_elems = show.select(".pic-tag .tag")
        rating = 0
        if rating_elems:
            rating = RATING_EXTRACTOR.search(rating_elems[0].text).group()
            rating = float(rating)

        show_id = link['href'].split("/")[2].split(".")[0]
        title = link["title"]
        thumbnail = link["data-original"]

        season_number = _get_season_number(title)
        shows.append({
            'label': title,
            'path': plugin.url_for("show_videos", show=show_id, season=season_number),
            'thumbnail': thumbnail,
            'icon': thumbnail,
            'poster': thumbnail,
            'info': {
                'mediatype': 'tvshow',
                'title': title,
                "season": season_number,
                "tvshowtitle": title,
                "rating": rating
            }
        })

    return shows


@plugin.route("/episodes/<show>/<season>/")
def show_videos(show, season):
    soup = _get_html(DUBOKU_URL + "/voddetail/" + show + ".html")
    episodes_elems = soup.select("#playlist2 li")
    if not episodes_elems or len(episodes_elems) == 0:
        episodes_elems = soup.select("#playlist1 li")
    episodes = []
    for i, episode in enumerate(episodes_elems):
        link = episode.find("a")
        href = link["href"]
        episode_path = href.split("/")[2]
        episode_text = link.text.strip()
        episode_number = "S{0}E{1}".format(season, i+1)

        episodes.append({
            "label": episode_number,
            "path": plugin.url_for("play_video", video_id=episode_path),
            "is_playable": True,
            "info": {
                "mediatype": "episode",
                "title": episode_text,
                "episode": i+1,
                "season": season
            }
        })

    return episodes


@plugin.route("/videos/<video_id>/")
def play_video(video_id):
    soup = _get_html(DUBOKU_URL + "/vodplay/" + video_id)
    player = soup.select(".myui-player__box")[0]
    match = URL_REGEX.search(str(player.find("script")))
    video_server = match.group(1)
    video_date = match.group(2)
    video_id = match.group(3)
    video_url = "https://{0}/{1}/{2}/hls/index.m3u8".format(
        video_server, video_date, video_id)
    plugin.log.info("Playing URL: {0}".format(video_url))
    plugin.set_resolved_url(video_url)


if __name__ == '__main__':
    plugin.run()
