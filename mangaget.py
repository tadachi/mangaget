import sys
import os
import logging
import glob
import fnmatch

import concurrent.futures
import urllib.parse
import gzip
import natsort
from pprint import pprint

# Pip install frameworks.
import requests
import eventlet
import click

# Custom parsers.
from mangabee_parsers import *
from mangahere_parsers import *

# Helpers.
from helper import *



###
### Config
###
logging.basicConfig(filename='mangaget.py.log', filemode='a+', level=logging.DEBUG)
requests_log = logging.getLogger("requests")
requests_log.setLevel(logging.WARNING) #Disable logging for requests by setting it to WARNING which we won't use.

###
### Functions
###

def search(manga_name, manga_site): # Makes 1 http request..
    mangabee_url  = 'http://www.mangabee.com/manga-list/search/%s/name-az/1' % mangabeeUrlify(manga_name)
    mangahere_url = 'http://www.mangahere.co/search.php?name=%s' % urllib.parse.quote(mangahereUrlify(manga_name))
    results       = None
    parser        = None

    if (manga_site == 'mangahere'):
        req = requestContentWithHeaders(mangahere_url)
        parser = mangahereSearchParser()
    elif (manga_site == 'mangabee'):
        req = requestContentWithHeaders(mangabee_url)
        parser = mangabeeSearchParser()
    else:
        printAndLogInfo("".join(['Not a valid manga site: ', manga_site, '. Try \'mangabee\' or \'mangahere\'']))
        return False

    parser.feed(req)         # req contains all the html from url.
    results = parser.urls    # Save our results.
    parser.close             # Free the parser resource.

    return results # Example: ['http://www.mangahere.co/manga/boku_to_kanojo_no_game_sensou/', 'http://www.mangahere.co/manga/no_game_no_life/', 'http://www.mangahere.co/manga/ore_to_ichino_no_game_doukoukai_katsudou_nisshi/']


def initializeSetup(url, manga_site): # Makes 1 http request..
    src      = None
    chapters = None
    pages    = None
    urls     = None

    if (manga_site == 'mangahere'):
        parser = mangahereVolumeChapterParser() # Grabs all the chapters from the manga's html page.
        req = requestWithHeaders(url)
        parser.feed(req.text)
        urls = parser.urls
        results = dict(chapter_urls=urls, search_url=url)
        parser.close

        return results # {['http://www.mangahere.co/manga/hack_legend_of_twilight/v03/c000.4/' ... 'http://www.mangahere.co/manga/hack_legend_of_twilight/v03/c000.3/'}
    elif (manga_site == 'mangabee'):
        chapter_urls = []
        parser = mangabeeSetupParser()
        req = requestWithHeaders(url + '1/1')

        parser.feed(req.text)

        # chapter_numbers = [e for e in parser.chapters if 'Raw' not in e] # all chapters with Raw are untranslated so filter them out.
        chapter_numbers = [e[:4] for e in parser.chapters]
        chapter_numbers = [onlyNumbers(e) for e in chapter_numbers] # Leave only the numbers floats and strip chracters such as -, whitespace.
        chapter_numbers = sorted(filter(None, chapter_numbers), key=float)

        for chapter_number in chapter_numbers:
            chapter_urls.append( "".join([url, chapter_number]))
        parser.close
        results = dict(chapter_urls=chapter_urls, search_url=url)

        return results # {'chapters': ['1', ... '9'], 'src': ['http://i3.mangareader.net/blood-c/1/blood-c-2691771.jpg'], 'url': ['http://www.mangabee.com/blood-c/1/1'], 'pages': ['1', ...', '40']}
    else:
        printAndLogInfo("".join(['Not a valid manga site: ', manga_site, '. Try \'mangabee\' or \'mangahere\'']))
        return False


def createMasterChapterIntegrityFile(setup, manga_site): # 0 http requests.
    chapter_urls        = natsort.natsorted(setup.get('chapter_urls')) # Nat sort because chapters can be named like this: c1, c2.. or 1, 2, 3..
    chapter_directories = []
    chapter_numbers     = []
    chapter_json_files  = []
    search_url          = setup.get('search_url')
    first_chapter_url   = chapter_urls[0] # http://www.mangahere.co/manga/hack_legend_of_twilight/v03/c000.4/
    root_directory      = manga_site  # root directory of where the manga is downloaded to.
    base_directory      = None        # directory that carries the name of the manga.
    manga_name          = None        # manga name that will be part of the chapter directory for that manga.
    directory           = None        # chapter directory.
    file_path           = None
    data                = {} # For our json integrity file that manages all the chapters.

    ### Create directories ###
    if (manga_site == 'mangahere'):
        if (len(first_chapter_url.split('/')) < 8):
            manga_name = first_chapter_url.rsplit('/',4)[2]  # volume based: ['http:', '', 'www.mangahere.co', 'manga', 'hack_legend_of_twilight', 'v01', 'c000', ''] count: 8
        else:
            manga_name = first_chapter_url.rsplit('/',4)[1]  # !volumebased: ['http:', '', 'www.mangahere.co', 'manga', 'tora_kiss_a_school_odyssey', 'c001.1', '']  count: 7
    elif (manga_site == 'mangabee'):
        manga_name = chapter_urls[0].rsplit('/',2)[1]  # parse the url for something like this this: 'tokyo_ghoul'

    if not os.path.exists(root_directory):
        os.mkdir(root_directory)           # directory: ..mangahere/ ..mangabee/
        logging.info("".join([timestamp(), ' Created directory: ', root_directory]))

    base_directory = os.path.join(root_directory, manga_name) # ..mangahere/tokyo_ghouls/ ..mangabee/tokyo_ghouls/
    if not os.path.exists(base_directory):
        os.mkdir(base_directory) # ..mangahere/tokyo_ghouls/ ..mangabee/tokyo_ghouls/
        logging.info("".join([timestamp(), ' Created directory: ', base_directory]))

    if (manga_site == 'mangahere'):
        for i in range( 0, len(chapter_urls) ):
            chapter_number = chapter_urls[i].rsplit('/',2)[1] # Use the part of the url for chapter numbering instead of var i in the for loop.
            chapter_directory = os.path.join( base_directory, "".join( [manga_name, '_', chapter_number] ) )  # 'mangahere\Tokyo_Ghoul\Tokyo_Ghoul\Tokyo_Ghoul_001 ... Tokyo_Ghoul_019 ... Tokyo_Ghoul_135'
            chapter_directories.append(chapter_directory)
            chapter_numbers.append(chapter_number)
        chapter_numbers = sorted(chapter_numbers)
        chapter_directories = sorted(chapter_directories)
    elif (manga_site == 'mangabee'):
        for i in range( 0, len(chapter_urls) ):
            chapter_number = chapter_urls[i].rsplit('/',1)[1]
            chapter_directory = os.path.join( base_directory, "".join([manga_name, '_', mangaNumbering(str(chapter_number))]) ) # 'manga/Tokyo_Ghoul/Tokyo_Ghoul/Tokyo_Ghoul_001 ... Tokyo_Ghoul_019 ... Tokyo_Ghoul_135'
            chapter_directories.append(chapter_directory)
            chapter_numbers.append(chapter_number)
        chapter_numbers = natsort.natsorted(chapter_numbers, key=float)
        chapter_directories = natsort.natsorted(chapter_directories)

    for i in range( 0, len(chapter_urls) ):
        if not os.path.exists(chapter_directories[i]):
            os.mkdir(chapter_directories[i])
        chapter_json_files.append("".join([chapter_directories[i], '.json']))

    file_path = os.path.join( root_directory, "".join([manga_name, '_', 'chapters.json']) )

    data['chapter_urls']        = chapter_urls #sorted(chapter_urls)
    data['chapter_directories'] = chapter_directories
    data['chapter_numbers']     = chapter_numbers
    data['root_directory']      = root_directory
    data['base_directory']      = base_directory
    data['chapter_json_files']  = chapter_json_files
    data['manga_name']          = manga_name
    data['search_url']          = search_url
    data['file_path']           = file_path
    writeToJson(data, file_path) # ../mangahere/akame_ga_kiru_chapters.json

    return data #Json data.


def updateIntegrityFiles(chapters_json_file, start=0, end=0): #Gets the manga_site from the master integrity file.
    json_data = open(chapters_json_file).read()
    data = json.loads(json_data)
    updated_json_files = data.get('chapter_json_files')
    chapter_numbers    = data.get('chapter_numbers')
    base_directory     = data.get('base_directory')
    chapter_urls       = data.get('chapter_urls')
    manga_name         = data.get('manga_name')
    manga_site         = data.get('root_directory')
    printAndLogInfo("".join([timestamp(), ' Building chapter integrity files. This can take awhile if there are many chapters. e.g 100+...']))
    if (end == 0 or end >= len(updated_json_files)):
        end = len(updated_json_files)
    if (start > 0):
        start -= 1
    #print("".join([str(start), ' and ', str(end)]))
    for i in range(start, end):
    # for i in range(0, 1): # Testing one chapter.
        if (os.path.isfile(updated_json_files[i])):
            pass
        else:
            if (manga_site == 'mangahere'):
                chapter_directory = os.path.join( base_directory, "".join( [manga_name, '_', chapter_numbers[i]] ) )
                createIntegrityChapterJsonFile(chapter_urls[i], base_directory, chapter_directory, chapter_numbers[i], updated_json_files[i], manga_site)
                printAndLogInfo("".join([timestamp(), ' Created ', updated_json_files[i]]))
            elif (manga_site == 'mangabee'):
                chapter_directory = os.path.join( base_directory, "".join( [manga_name, '_', mangaNumbering(str(chapter_numbers[i]))] ) )
                createIntegrityChapterJsonFile(chapter_urls[i], base_directory, chapter_directory, chapter_numbers[i], updated_json_files[i], manga_site)
                printAndLogInfo("".join([timestamp(), ' Created ', updated_json_files[i]]))
    return True


def createIntegrityChapterJsonFile(chapter_url, base_directory, directory, chapter_number, chapter_json_file, manga_site):
    pages_and_src     = []
    page_urls         = [] # Holds a reference to the image on mangahere's CDN. You need to parse its HTML for that CDN image link.
    page_numbers      = []
    pages_src         = [] # Holds all the urls to the images on Mangahere's CDN.
    image_files_paths = []

    req = requestWithHeaders(chapter_url)  # Makes 1 http request.s

    if (manga_site == 'mangahere'):
        parser = mangahereHTMLGetImageUrls()
        parser.feed(req.text)
        page_urls = parser.page_urls
        page_numbers = parser.page_numbers
    elif (manga_site == 'mangabee'):
        parser = mangabeeHTMLGetImageUrls()
        parser.feed(req.text)
        page_numbers = parser.page_numbers
        for page_number in page_numbers:
            page_urls.append("".join([chapter_url, '/', page_number]))

    parser.close # Close parser to free it.

    for page in page_numbers:
        file_path = "".join([directory, '\\', mangaNumbering(page), '.jpg'])
        image_files_paths.append( file_path )

    pages_and_src = buildPagesAndSrc(page_urls, page_numbers, manga_site) # Makes multiple requests
    pages_and_src = sorted(pages_and_src, key=lambda k: k['page'])

    for dic in pages_and_src:
        pages_src.append(dic.get('src'))

    length = len(pages_and_src)

    ### Create integrity json file ###
    if ( len(pages_and_src) == len(image_files_paths) == len(page_urls) == len(page_numbers) ): # Number of items in each match so proceed.
        data = generateChapterIntegrityData(directory, base_directory, chapter_url, image_files_paths, pages_and_src, pages_src, length, chapter_number , 'Not Downloaded.')

        writeToJson(data, chapter_json_file)
    else:
        logging.debug("".join([timestamp(), ' Number of image_srcs, file_paths, and page_urls do not match. Check page numbering for that chapter on mangahere', image_files_paths[0]]))
        return False

    return True


def downloadManga(master_json_file, index=0):
    def download(data):
        pages_src         = data.get('pages_src')
        image_files_paths = data.get('image_files_paths')
        chapter_url       = data.get('chapter_url')
        base_directory    = data.get('base_directory')
        directory         = data.get('directory')

        if (data['downloaded'] == 'Not Downloaded.'):
            printAndLogInfo("".join(['\nDownloading ', data.get('chapter_url'), ' ...\n']))
            downloadConcurrently( pages_src, image_files_paths )
            data['downloaded'] = 'Downloaded'
            logging.info("".join([timestamp(), ' ', chapter_url, ' successfully downloaded.']))
            seconds = str(randomSleep(1,2)) # Introduce an artificial delay after you downloaded a whole chapter.
            print("".join(['Downloaded. Waited ', seconds, ' seconds to prevent being timedout by server...']))
            writeToJson(data, "".join([directory, '.json']))
        else:
            print("".join([chapter_url, ' Already downloaded']))

    master_json_data = open(master_json_file).read()
    master_data = json.loads(master_json_data)
    if (not index): # If there isn't a chapter range specified
        for json_file in master_data.get('chapter_json_files'):
            json_data = open(json_file).read()
            data = json.loads(json_data)
            download(data)
    elif(index[0] == 0 and index[0] == 0):
        for json_file in master_data.get('chapter_json_files'):
            json_data = open(json_file).read()
            data = json.loads(json_data)
            download(data)
    else: # If there is a chapter range specified: (1, 3) = chapters from 1 to 3 download.
        i = 0
        for json_file in master_data.get('chapter_json_files'):
            if i in range(index[0]-1, index[1]):
                json_data = open(json_file).read()
                data = json.loads(json_data)
                download(data)
            i += 1


def generateChapterIntegrityData(directory, base_directory, chapter_url, image_files_paths, pages_and_src, pages_src, length, chapter_number , downloaded):
    data = {}
    ### Build a manga chapter integrity json file. ###
    data['downloaded']        = downloaded
    data['chapter_number']    = chapter_number
    data['len']               = length
    data['pages_and_src']     = pages_and_src
    data['pages_src']         = pages_src
    data['image_files_paths'] = image_files_paths
    data['chapter_url']       = chapter_url
    data['directory']         = directory
    data['base_directory']    = base_directory

    return data


def buildPagesAndSrc(page_urls, page_numbers, manga_site): # Multiple Requests.
    pages_and_src = []
    if (manga_site == 'mangahere'):
        parser = mangahereHTMLGetImageSrcs()
    elif (manga_site == 'mangabee'):
        parser = mangabeeHTMLGetImageSrcs()

    ### Concurrently find image src on each html page. ###
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor: # Multiple (small) requests. max_workers Was 15 but was too slow.
        # Download the load operations and mark each future with its URL
        future_to_url = {executor.submit(requestContentWithHeadersAndKey, url, page): [url,page] for url,page in zip(page_urls,page_numbers)}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                html_data = future.result()
                parser.feed(html_data.get('html'))
                pages_and_src.append( {'page': mangaNumbering(html_data['page']), 'src':parser.src} )
                parser.reset # Clear contents of parser.
            except Exception as exc:
                printAndLogDebug( timestamp(), ' %r generated an exception: %s' % (url, exc) )


    return pages_and_src


def checkChapterIntegrity(search_string, manga_site):
    def update(search_result, manga_site):
        master_json_file = "".join([search_result, '_', 'chapters.json'])
        json_data = open(master_json_file).read() # akame_ga_kiru_chapters.json
        data = json.loads(json_data)

        setup = dict(chapter_urls=data.get('chapter_urls'), search_url=data.get('search_url'))

        createMasterChapterIntegrityFile(setup, manga_site)
        updateIntegrityFiles(master_json_file)

    search_string = "".join(['*',search_string,'*'])
    if (manga_site == 'mangahere'):
        search_results = glob.glob("".join(os.path.join('mangahere',search_string)))
    elif (manga_site == 'mangabee'):
        search_results = glob.glob("".join(os.path.join('mangabee',search_string)))
    else:
        printAndLogInfo( "".join(['No such manga site.']) )

    index = 888
    for result in search_results: # Remove all instances of .json when selecting a manga to fix.
        if fnmatch.fnmatch(result, '*.json'):
            search_results.remove(result)

    if (len(search_results) == 1): # only one choice so..

        update(search_results[0], manga_site)
        json_files = glob.glob(os.path.join(search_results[0], '*.json'))

        for json_file in json_files:
            verify(json_file)
            pass

    # Example choices:
    # 0. mangahere\muvluv_alternative
    # 1. mangahere\muvluv_alternative_total_eclipse
    elif (len(search_results) > 1):
        for i in range(0, len(search_results)): # Make sure it's within our search results.
            print("".join([str(i), '. ', search_results[i]])) # Display choices of manga to check its integrity.

        try: # Ask for which manga to check.
            index = int(input('Enter a number: ')) # Get the number.
        except (KeyboardInterrupt, SystemExit): # This catches empty strings and makes it so it keeps asking for input.
            raise
        except ValueError: # This catches empty strings and makes it so it keeps asking for input.
            index = index
        except: # Catch-all particularly KeyboardInterrupt.
            printAndLogInfo('\nCancelling...')
            exit()

        update(search_results[index])

        json_files = glob.glob(os.path.join(search_results[index], '*.json'))
        if (json_files):
            for json_file in json_files:
                verify(json_file)
        else:
            printAndLogInfo("".join([timestamp(), ' No integrity json file found in ',search_results[index], '.']))
    else:
        printAndLogInfo("".join([timestamp(), ' No such manga found.']))


def verify(json_file):
    json_data = open(json_file).read()
    data = json.loads(json_data)
    printAndLogInfo( "".join([timestamp(), ' Verifying ', data.get('directory') , '...']) )

    img_file_count = imageFileCount(data.get('directory'))
    directory = data.get('directory')

    if ( data.get('downloaded') == 'Not Downloaded' or int(img_file_count) != int(data.get('len')) ):

        if not os.path.exists(directory):
            os.mkdir(directory) # ..mangahere/tokyo_ghouls/
            logging.info("".join([timestamp(), ' Created directory: ', directory]))

        pages_src = []
        for dic in data.get('pages_and_src'):
            pages_src.append(dic.get('src'))

        downloadConcurrently(pages_src, data.get('image_files_paths')) # Parameter examples: http://z.mhcdn.net/store/manga/3249/01-001.0/compressed/gokko_story01_w.s_001.jpg?v=11216726214d, "mangahere\\gokko\\gokko_c001\\001.jpg" ...
        data['downloaded'] = 'Downloaded'
        printAndLogInfo( "".join([data.get('chapter_url'), ' Chapter downloaded successfully.']) )
        seconds = str(randomSleep(3,5)) # Introduce a longer delay after you downloaded a whole chapter.
        print("".join(['waiting ', seconds, ' seconds...']))
        writeToJson(data, json_file) # Write again and specify that the whole chapter is downloaded successfully.
    else:
        if ( int(img_file_count) == int(data.get('len')) ):
            printAndLogInfo( "".join([timestamp(), ' ', data.get('directory'), ' Integrity check is good for this chapter.']) )
        else:
            printAndLogDebug( "".join([timestamp(), ' ', data.get('directory'), ' Integrity check failed. Something went deeply wrong. File a bug report please.']) )


def mangaNumbering(s):
    if (len(s) == 1):
        return "".join(['00',s])
    elif (len(s) == 2):
        return "".join(['0',s]) # 019, 020, 021 ...
    elif (len(s) == 3):
        return s                # 100, 211, 321 ... 599

    logging.info('Abnormal numbering encountered') # Multiple requests.
    return "".join(['0',s])


def downloadConcurrently(urls, paths):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor: # Multiple requests.
        for path,url in zip(paths, urls):
            executor.submit(requestFile, path, url)
            randomSleep(0,1)
    return True


def requestFile(output, url):
    with open(output, 'wb') as f:
        response = requests.get(url, stream=True)
        writeBytes(int(response.headers.get('Content-Length')))
        print("".join(['Downloading ', url, ' to ', output]))

        if not response.ok:
            print("".join(['Could not download from: ', url]))
            logging.debug( "".join([timestamp(), ' Could not download from: ', url]))
            return False

        for chunk in response.iter_content(1024):
            f.write(chunk)

    return True


def requestWithHeaders(url):
    headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36',
                'Content-Type':'text/plain; charset=utf-8', 'Accept':'*/*', 'Accept-Encoding':'gzip,deflate,sdch,text'}
    req = requests.get(url, headers = headers)

    writeBytes(sys.getsizeof(req)) # Add bandwidth usage (GZIP compressed.)

    return req


def requestContentWithHeaders(url):
    headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36',
                'Content-Type':'text/plain; charset=utf-8', 'Accept':'*/*', 'Accept-Encoding':'gzip,deflate,sdch,text'}
    req = requests.get(url, headers = headers)

    writeBytes(sys.getsizeof(req)) # Add bandwidth usage (GZIP compressed.)

    return req.text


def requestContentWithHeadersAndKey(url, key):
    headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36',
                'Content-Type':'text/plain; charset=utf-8', 'Accept':'*/*', 'Accept-Encoding':'gzip,deflate,sdch,text'}
    req = requests.get(url, headers = headers)

    writeBytes(sys.getsizeof(req)) # Add bandwidth usage (GZIP compressed.)

    return {'page':key, 'html': req.text}


def writeBytes(b):
     global bytes
     bytes += b

def printAndLogInfo(string):
    print(string)
    logging.info(string)

def printAndLogDebug(string):
    print(string)
    logging.debug(string)

bytes = 0 # Keep track of bytes used.

@click.command()
@click.option('--manga_site', default='mangahere', help='Usage: mangaget.py --manga_site=mangabee bleach\nAvailable: mangahere mangabeet')
@click.option('--check', default=False, help='Usage: mangaget.py --check=True naruto\nDownload ALL manga chapters you are missing. And redownloads chapter if it is missing pages. Gives a choice if there are similar manga names.')
@click.option('--no_dl', default=0, help='Usage: mangaget --no_dl=True naruto\nJust searches.')
@click.option('--select', default=(0,0), nargs=2, type=int, help='Usage: mangaget --select 1 3 naruto\n...--select 4 4 ...\t\t\tto download only chapter 4')
@click.argument('search_term')

def mangaget(search_term, select, manga_site, no_dl, check):
    global bytes
    """A program that downloads manga from mangahere and mangabee."""
    index = 888

    if (select):
        if (select[1] < select[0]):
            print('Not a valid manga range. try ...--select 1 3... downloads chapters 1 to 3')
            print('If you want to download only one chapter, try ...--select 5 5...')
            exit()
        elif (select[0] < 0 or select[1] < 0):
            print('Range cannot be negative.')
            exit()
        elif (select[0] == 0 and select[1] >= 0):
            #print('Generating integrity json files for all chapters..')
            pass

    if (manga_site == 'mangahere' or manga_site == 'mangabee'):
        pass
    else:
        printAndLogInfo('Not a valid manga site')

    if (check): ## --check integrity of selected manga.
        checkChapterIntegrity(search_term, manga_site)
    else:
        ### Search for manga on manga site ###
        search_results = search(search_term, manga_site)
        printAndLogInfo("".join([timestamp(), ' Searching ', search_term, ' on ', manga_site, '...\n']))
        if (search_results):
            while index >= len(search_results):
                print('Pick a mangalink: ')
                for i in range(0, len(search_results)): # Make sure it's within our search results.
                    print("".join([str(i), '. ', search_results[i]]))
                try:
                    index = int(input('Enter a number: ')) # Get the number.
                except (KeyboardInterrupt, SystemExit): # This catches empty strings and makes it so it keeps asking for input.
                    raise
                except ValueError: # This catches empty strings and makes it so it keeps asking for input.
                    index = index
                except: # Catch-all particularly KeyboardInterrupt.
                    printAndLogInfo('\nCancelling...')
                    exit()
            logging.info("".join([timestamp(), ' Search Returned: ', search_results[0]]))
        else:
            printAndLogInfo("".join([timestamp(), ' Searching \'', search_term, '\' did not return anything. Exiting...']))
            exit()

        if (no_dl): # Don't download if set.
            exit()

        setup = initializeSetup(search_results[index], manga_site) # Initialize the downloading process.
        chapter_json_file = createMasterChapterIntegrityFile(setup, manga_site)
        updateIntegrityFiles(chapter_json_file.get('file_path'), select[0], select[1])
        downloadManga(chapter_json_file.get('file_path'), select)

    printAndLogInfo("".join([timestamp(), ' Finished... ', 'Usage: ', str(sizeMegs(bytes)), 'MB']))
    printAndLogInfo("".join([timestamp(), ' Finished... ', 'Usage: ', str(sizeKilo(bytes)), 'KB', '\n']))

###
### Main
###
def main(): # For debugging specific functions
    pass

if __name__ == "__main__":
    # main() # For debugging specific functions
    mangaget()
