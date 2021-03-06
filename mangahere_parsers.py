from html.parser import HTMLParser
import re

def onlyNumbers(s):
    s = re.sub(r'[^\d.]+', '', s) # Remove all characters and whitespace
    return s

class mangahereSearchParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.inLink = False
        self.lastTag = None
        self.lastClass = None
        self.urls = []         # Where we store our results
    def handle_starttag(self, tag, attrs):
        if (tag == 'div'):
            self.lastTag = 'div'
            attrs = dict(attrs)
            if (attrs.get('class') == 'result_search'):
                self.inLink = True
                self.lastClass ='result_search'

        if (self.lastTag == 'div' and tag == 'dl'):
            self.lastTag = 'dl'
        if (self.lastTag == 'dl' and tag == 'a' and self.lastClass == 'result_search'):
            attrs = dict(attrs)                            # example output: {'href': 'http://www.mangahere.co/manga/blood_c/'}
            if (attrs.get('class') == 'manga_info name_one'):
                self.urls.append( attrs.get('href') )     #['http://www.mangahere.co/manga/blood_c/', ...]

    def handle_endtag(self, tag):
        if (tag == 'div'):
            self.inLink = False
            self.lastTag = None
            self.lastClass = None

    def handle_data(self, data):
        pass

class mangahereVolumeChapterParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.inLink = False
        self.lastTag = None
        self.lastClass = None
        self.urls = []         # Where we store our results

    def handle_starttag(self, tag, attrs):
        if (tag == 'div'):
            self.lastTag = 'div'
            attrs = dict(attrs)
            if (attrs.get('class') == 'detail_list'):
                self.inLink = True
                self.lastClass ='detail_list'
            if (attrs.get('class') == 'all_commet'): # We want to stop here and not process facebook comments that link to other manga.
                self.inLink = False
                self.lastTag = None
                self.lastClass = None

        if (tag == 'div'):
            self.lastTag = 'div'
            attrs = dict(attrs)
            if (attrs.get('class') == 'chapters_points clearfix'):
                self.inLink = True
                self.lastTag = 'div'
                self.lastClass = 'chapters_points clearfix'


        if (tag == 'a' and self.lastClass == 'detail_list'):
            self.lastTag = 'a'
            attrs = dict(attrs)
            self.urls.append( attrs.get('href') )     #['http://www.mangahere.co/manga/hack_legend_of_twilight/v03/c000.4/'] or ['http://www.mangahere.co/manga/blood_c/c009/]

    def handle_endtag(self, tag):
        if (tag == 'div' and self.lastClass == 'chapters_points clearfix'):
            self.inLink = True
            self.lastTag = 'div'
            self.lastClass = 'detail_list'
        pass

    def handle_data(self, data):
        pass

class mangahereHTMLGetImageUrls(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.inLink = False
        self.lastTag = None
        self.lastClass = None
        self.page_numbers = []
        self.page_urls = []
        self.second_occurrence_pages = False
        self.second_occurrence_urls = False

    def handle_starttag(self, tag, attrs):
        if (tag == 'select'): # The tag with pages data.
            self.inLink = True
            attrs = dict(attrs)
            self.lastTag = 'select'
            if (attrs.get('class') == 'wid60'):
                self.lastClass = 'wid60'

        if (tag == 'option' and self.lastClass == 'wid60' and self.second_occurrence_urls == False):
            self.inLink = True
            self.lastTag = 'option'
            attrs = dict(attrs)
            self.page_urls.append(attrs.get('value')) #['http://www.mangahere.co/manga/code_geass_nightmare_of_nunnally/v01/c001/' ... 'http://www.mangahere.co/manga/code_geass_nightmare_of_nunnally/v01/c001/42.html']

    def handle_endtag(self, tag):
        if (tag == 'select' and self.lastClass == 'wid60'): # The tag with chapter data.
            self.inLink = False
            self.lastTag = None
            self.lastClass = None
            self.second_occurrence_pages = True
            self.second_occurrence_urls = True

    def handle_data(self, data):
        if (self.lastTag == 'option' and self.lastClass == 'wid60' and self.second_occurrence_pages == False):
            if (onlyNumbers(data) != ''): # Some garbage gets picked up on the way so you have to filter it.
                self.page_numbers.append(onlyNumbers(data))
        pass

class mangahereHTMLGetImageSrcs(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.inLink = False
        self.lastTag = None
        self.lastClass = None
        self.src = None

    def handle_starttag(self, tag, attrs):
        if (tag == 'section'): # The tag with pages data.
            self.inLink = True
            attrs = dict(attrs)
            self.lastTag = 'section'
            if (attrs.get('class') == 'read_img'):
                self.lastClass = 'read_img'

        if (tag == 'img' and self.lastClass == 'read_img'):
            self.inLink = True
            self.lastTag = 'option'
            attrs = dict(attrs)
            self.src = attrs.get('src')

    def handle_endtag(self, tag):
        if (tag == 'section'):
            self.inLink = False
            self.lastTag = None
            self.lastClass = None


    def handle_data(self, data):
        pass
