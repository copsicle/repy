"""
import pip._internal as pip
pip.main(['install', '-q', 'praw', 'psaw', 'scikit-image', 'matplotlib',
'psycopg2-binary', 'numpy', 'pillow', 'configparser', 'imgurpython'])
# I <3 Stack Overflow
"""
import praw
import os
import requests
import psycopg2
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
            exec(input("Insert Commands (data, red) >>> "))
        except Exception as e:
            print(f"An exception has occured in the mod console (continuing...):\n{e}")
            continue


def revert(db, red, theid):
    # Reverts removal of a post via this bot, can be ran in the modconsole
    sm = red.submission(id=theid)
    sm.mod.approve()
    with db.cursor() as cur:
        cur.execute("UPDATE repy SET Removed = false, Type = %s, RMID = NULL WHERE PostID = %s;",
                    (submission_sort(sm), theid))
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
                    "RMID varchar(10));")
    # PostID - Submission ID, Type - what kind of submission is it, Removed - is the post removed,
    # RMID - the sm id which looked similar to this if it was removed (null if it wasn't)
    data.commit()
    return is_db_empty(data)


def get_image(sm, imgr):
    # Get a url for the submission id and then open it as float for later operations
    # print(sm.domain)
    # print(type(sm.domain))
    url = sm.url
    if submission_sort(sm) == "video": url = sm.thumbnail
    if sm.domain == 'imgur.com':
        splitlink = url.split("/")
        if splitlink[-2:][0] == "a": url = imgr.get_album_images(splitlink[-1:][0])[0].link
        else: url = imgr.get_image(splitlink[-1:][0]).link
    print(f"Got an image on this url : {url}")
    response = requests.get(url)
    return Image.open(BytesIO(response.content)), url.split(".")[-1:][0]


def create_image_path():
    # Creates a folder to store images
    directory = ".\\images"
    if os.path.exists(directory): return os.listdir(directory)
    os.makedirs(directory)
    return None


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
    # The line below makes the submission object actually get all the attributes from the api since it starts empty
    print(sm.title)
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
    with database.cursor() as cur:
        cur.execute(f"SELECT {column} FROM repy {where};")
        return list(cur.fetchall())


"""
def get_ids(datab, rmd):
    # Gets ids of all removed/not removed submissions in the db
    no = "WHERE Removed"
    if rmd is None: no = ""
    elif not rmd: no = "WHERE NOT Removed"
    dalist = get_from_db(datab, "PostID", no)
    if dalist is None: return None
    return dalist
"""


def get_row(datab, sm):
    # Gets info about a submission in the database
    nice = get_from_db(datab, "*", f"WHERE PostID = {sm.id}")
    if nice is None: return None
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
    if submi.author is None or submi.selftext == '[removed]' or submi.selftext == '{deleted]': return "removed"
    elif submi.is_self: return "text"
    elif submi.is_video: return "video"
    elif submi.domain == "i.redd.it" or submi.domain == "imgur.com": return "image"
    # It's janky but it works™
    return "link"


def archive(red, suby):
    # Get every post in a subreddit since Reddit's creation in 2005 (the api doesn't go this far anyways)
    return PushshiftAPI(red).search_submissions(after=1119484800, subreddit=suby.display_name)


def add_to_db(db, subm, rmid):
    # Add a submission to the database
    bool1 = False
    if rmid: bool1 = True
    with db.cursor() as cur:
        cur.execute("INSERT INTO repy (PostID, Type, Removed, RMID) VALUES (%s, %s, %s, %s);",
                    (subm.id, submission_sort(subm), bool1, rmid))
    db.commit()


def remove_submission(db, subm, rmsm):
    # Remove a submission from the database and Reddit (only with an original submission)
    copypasta = "Your submission was removed because it is a suspected repost. The post that collides with yours can" \
        f" be found [here](http://www.reddit.com{rmsm.permalink})." \
        "\n \n ^(I am a bot, this action was performed automatically.) " \
        "\n \n ^(If you have any questions or you believe I am wrong please contact to moderators of the subreddit)" \
        "\n \n ^(All of my code is visible [here](https://github.com/copsicle/repy))"
    if not subm == rmsm:
        subm.mod.send_removal_message(copypasta, title="repost")
        subm.mod.remove()
    with db.cursor() as cur:
        cur.execute("UPDATE repy SET Removed = true, Type = %s, RMID = %s WHERE PostID = %s",
                    ("removed", rmsm.id, subm.id))
    db.commit()


def remove_image(subm):
    directory = ".\\images"
    for image in os.listdir(directory):
        if subm.id in image:
            os.remove(directory + "\\" + image)
            break


def db_to_ram(red, imger, db):
    submissions = []
    for ids in get_from_db(db, "PostID, Type, Removed", ""):
        print(ids[0])
        sm = red.submission(id=ids[0])
        ss = submission_sort(sm)
        if ss == "removed":
            if not ids[2]:
                if ids[1] == "image" and find_image(sm) is not None: remove_image(sm)
                remove_submission(db, sm, sm)
                continue
        if ss == "removed" and ids[2]: continue
        if ids[1] == "image" and find_image(sm) is None: save_image(sm, imger)
        submissions.append(RepySubmission(ids[0], ss, sm.url, sm.selftext, sm.permalink))
    return submissions


def is_db_empty(db):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM repy;")
        if cur.fetchone() is not None: return False
    return True


def is_original(sm, smlist, detection):
    for repysubmission in smlist:
        if sm.url == repysubmission.url: return False, repysubmission
    if sm.type == "image" or sm.type == "video":
        original = find_image(sm)
        for repysubmission in smlist:
            if repysubmission.type == "image" or repysubmission.type == "video":
                if compare_images(original, find_image(repysubmission)) > detection: return False, repysubmission
    elif sm.type == "text":
        for repysubmission in smlist:
            if repysubmission.type == "text":
                if compare_text(sm, repysubmission) > detection: return False, repysubmission
    return True


class RepySubmission:
    # A simple class that shadows the Submission object, meant for efficient information access for quick operations
    def __init__(self, id, type, url, selftext, permalink):
        self.id = id
        self.type = type
        self.url = url
        self.text = selftext
        self.permalink = permalink
