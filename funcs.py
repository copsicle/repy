"""
import pip._internal as pip
pip.main(['install', '-q', 'praw', 'psaw', 'scikit-image', 'matplotlib',
'psycopg2-binary', 'numpy', 'pillow', 'configparser', 'imgurpython'])
"""
import praw, os, requests, psycopg2
import matplotlib.pyplot as plt
# import numpy as np
from configparser import RawConfigParser as Parse
from PIL import Image
from io import BytesIO
from imgurpython import ImgurClient
from psaw import PushshiftAPI
# from multiprocessing import pool
# from time import sleep
# from pprint import pprint
from skimage import img_as_float
from skimage.measure import compare_ssim as ssim
from skimage.transform import resize


def get_ini(ininame):
    # Get credentials via ini, requires string of file name
    config = Parse()
    config.read(ininame)
    return config


def reddit_session(cfg):
    # Start a connection with Reddit using credentials from the ini
    red = praw.Reddit(client_id=cfg['reddit']['clientid'],
                      client_secret=cfg['reddit']['secret'],
                      password=cfg['reddit']['password'],
                      user_agent=cfg['reddit']['useragent'],
                      username=cfg['reddit']['username'])
    sub = red.subreddit(cfg['reddit']['subreddit'])
    print("Connected to Reddit on r/" + str(sub))
    return red, sub


def imgur_session(cfg):
    # Start a connection with Imgur using credentials from the ini
    return ImgurClient(cfg['imgur']['icid'], cfg['imgur']['icis'])


def connect_to_db(cfg):
    # Connect to the local database
    return psycopg2.connect(dbname=cfg['database']['name'],
                            user=cfg['database']['username'],
                            password=cfg['database']['password'])


def mod_console(data, red, cfg):
    # Console to run commands manually while the code is running, should be ran in its own thread
    while True:
        try:
            eval(input("Insert Commands (data, red) >>> "))
        except (SyntaxError, RuntimeError):
            continue


def revert(db, red, theid):
    # Reverts removal of a post via this bot, can be ran in the modconsole
    sm = red.submission(theid)
    sm.mod.approve()
    with db.cursor() as cur:
        cur.execute(f"UPDATE repy SET Removed = false AND RMID = NULL WHERE PostID = {theid};")
    db.commit()


def close(db):
    # Shuts down the bot safely and rolls back any changes to the database
    db.rollback()
    db.close()
    raise SystemExit


def new_table(data):
    # Creates a new table in the db schema if it doesn't exist already
    with data.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS repy "
                    "(PostID varchar(10) NOT NULL,"
                    "Type varchar(10) NOT NULL,"
                    "Removed boolean DEFAULT false,"
                    "RMID varchar(10);")
    # PostID - Submission ID, Type - what kind of submission is it, Removed - is the post removed,
    # RMID - the sm id which looked similar to this if it was removed (null if it wasn't)
    data.commit()


def get_image(sm, imgr):
    # Get a url for the submission id and then open it as float for later operations
    # print(sm.domain)
    # print(type(sm.domain))
    url = sm.url
    if sm.domain == 'imgur.com':
        img = imgr.get_image(url.split("/")[-1:][0])
        url = img.link
    print(f"Got an image on this url : {url}")
    response = requests.get(url)
    return Image.open(BytesIO(response.content)), url.split(".")[-1:][0]


def create_image_path():
    # Creates a folder to store images
    directory = ".\\images"
    if os.path.exists(directory):
        return len([thing for thing in os.listdir(directory)])
    else:
        os.makedirs(directory)
    return 0


def get_image_resizing_params(im1, im2):
    # Checks and returns the smallest dimensions within two images
    results = []
    for x in range(2):
        results.append(min(im1.shape[x], im2.shape[x]))
    return results[0], results[1]


def resize_images(length, width, fimg, simg):
    # Image downscaling phase, resizing both because ssim does not seem to work with a non operated image
    print(f"Resizing two images to X : {str(width)} Y : {str(length)}")
    return resize(fimg, (length, width)), resize(simg, (length, width))


def compare_images(im1, im2):
    # SSIM the images
    img1, img2 = img_as_float(im1), img_as_float(im2)
    l, w = get_image_resizing_params(img1, img2)
    rimg1, rimg2 = resize_images(l, w, img1, img2)
    return ssim(rimg1, rimg2, multichannel=True)


def save_image(sm, imger):
    # Save the image
    directory = ".\\images"
    img, frmt = get_image(sm, imger)
    if img.mode == "RGBA" and frmt == "jpg": img = img.convert("RGB")
    img.save(f"{directory}\\{sm.id}.{frmt}")


def compare_text(sm1, sm2):
    # Compare two texts to detect copypasta
    str1, str2 = sm1.selftext, sm2.selftext
    a, b = set(str1.split()), set(str2.split())
    c = a.intersection(b)
    return float(len(c)) / (len(a) + len(b) - len(c))


def get_attributes(sm):
    # Saves to a text file all the attributes a specific submission object has
    sm.title
    with open('attributes.txt', 'w') as af:
        for line in vars(sm):
            af.write(f"{line}\n")
    print("File written successfully")


def find_image(sm):
    # Finds an image in the folder via searching by id
    directory = ".\\images"
    for image in os.listdir(directory):
        if sm.id in image:
            directory += f"\\{image}"
            return Image.open(directory)


def get_from_db(database, column, where):
    # Gets something from the database
    listy = []
    with database.cursor() as cur:
        cur.execute(f"SELECT {column} FROM repy {where};")
        for tp in cur.fetchall():
            listy.append(tp[0])
    return listy


def get_ids(datab, rmd):
    # Gets ids of all removed/not removed submissions in the db
    no = "WHERE Removed"
    if rmd is None : no = ""
    elif not rmd : no = "WHERE NOT Removed"
    dalist = get_from_db(datab, "PostID", no)
    if dalist is None: return None
    return dalist


def get_row(datab, sm):
    # Gets info about a submission in the database
    nice = get_from_db(datab, "*", f"WHERE PostID = {sm.id}")
    if nice is None : return None
    return nice


def show_images(image1, image2):
    # Show two images
    fig, axes = plt.subplots(nrows=1, ncols=2)
    ax = axes.ravel()
    ax[0].imshow(img_as_float(image1))
    ax[0].set_title("The first image")
    ax[1].imshow(img_as_float(image2))
    ax[1].set_title("The second image")
    plt.tight_layout()
    plt.show()


def submission_sort(submi):
    # Returns a string which specifies what type of post is given
    if submi.author is not None:
        if submi.is_self: return "text"
        elif submi.is_video: return "video"
        elif len(submi.url.split(".")[-1]) == 3 or len(submi.url.split(".")[-1]) == 4 \
                or submi.domain == "imgur.com": return "image"
        # It's janky but it works(tm)
        return "link"
    elif submi.selftext == "[deleted]": return "removed"


def archive(red, suby):
    # Get every post in a subreddit since Reddit's creation in 2005 (the api doesn't go this far anyways)
    api = PushshiftAPI(red)
    ids = api.search_submissions(after=1119484800, subreddit=suby.display_name)
    for did in ids:
        print(f"{did} is {submission_sort(red.submission(id=did))}")


def add_to_db(db, subm, rmid):
# Add a submission to the database
    bool = False
    if rmid: bool = True
    with db.cursor() as cur:
        cur.execute("INSERT INTO repy (PostID, Type, Removed, RMID) "
                    f"VALUES ({subm.id}, {submission_sort(subm)}, {bool}, {rmid});")


# def the_final_solution(red, sub, imger, db):

