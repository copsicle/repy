"""
import pip._internal as pip
pip.main(['install', '-q', 'praw', 'scikit-image', 'matplotlib', 'psycopg2', 'numpy', 'pillow', 'configparser', 'imgurpython'])
"""
import praw, os, requests, psycopg2, threading, sys
import matplotlib.pyplot as plt
# import numpy as np
from configparser import RawConfigParser as Parse
from PIL import Image
from io import BytesIO
from imgurpython import ImgurClient
#from time import sleep
from pprint import pprint
from skimage import img_as_float
from skimage.measure import compare_ssim as ssim
from skimage.transform import resize


def get_ini(ininame):
    config = Parse()
    config.read(ininame)
    return config


def reddit_session(cfg):
    # Start a connection with Reddit using credentials in an ini file
    red = praw.Reddit(client_id=cfg['reddit']['clientid'],
                      client_secret=cfg['reddit']['secret'],
                      password=cfg['reddit']['password'],
                      user_agent=cfg['reddit']['useragent'],
                      username=cfg['reddit']['username'])
    sub = red.subreddit(cfg['reddit']['subreddit'])
    print("Connected to Reddit on r/" + str(sub))
    return red, sub


def imgur_session(cfg):
    return ImgurClient(cfg['imgur']['icid'], cfg['imgur']['icis'])


def connect_to_db(cfg):
    return psycopg2.connect(dbname=cfg['database']['name'],
                            user=cfg['database']['username'],
                            password=cfg['database']['password'])


def mod_console(data, red, cfg):
    while True:
        try:
            eval(input("Insert Commands (data, red) >>> "))
        except (SyntaxError, RuntimeError):
            continue


def revert(db, red):
    theid, cur = input("Enter ID >>> "), db.cursor()
    sm = red.submission(theid)
    sm.mod.approve()
    cur.execute(f"UPDATE r9k SET Removed = false WHERE PostID = {theid};")
    cur.close()
    db.commit()


def close(db):
    db.rollback()
    db.close()
    raise SystemExit


def new_table(data):
    cur = data.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS r9k "
                "(PostID varchar(10) NOT NULL,"
                "Type varchar(10) NOT NULL,"
                "Removed boolean DEFAULT false,"
                "RMID varchar(10);")
    # PostID - Submission ID, Type - what kind of submission is it, Removed - is the post removed,
    # RMID - the sub id which looked similar to this if it was removed
    cur.close()
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
    directory = ".\\images"
    if os.path.exists(directory):
        return len([thing for thing in os.listdir(directory)])
    else:
        os.makedirs(directory)
    return 0


def get_image_resizing_params(im1, im2):
    # Checks and returns the smallest dimensions within two images
    i1s, i2s, results = None, None, []
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
    directory = ".\\images"
    img, frmt = get_image(sm, imger)
    if img.mode == "RGBA" and frmt == "jpg": img = img.convert("RGB")
    img.save(f"{directory}\\{sm.id}.{frmt}")


def compare_text(sm1, sm2):
    str1, str2 = sm1.selftext, sm2.selftext
    a, b = set(str1.split()), set(str2.split())
    c = a.intersection(b)
    return float(len(c)) / (len(a) + len(b) - len(c))


def get_attributes(sm):
    sm.title
    attfile = open('attributes.txt', 'w')
    for line in vars(sm):
        print(line)
        attfile.write(f"line\n")
    attfile.close()


def find_image(sm):
    directory = ".\\images"
    for image in os.listdir(directory):
        if sm.id in image:
            directory += f"\\{image}"
            return Image.open(directory)
    return None


def get_from_db(database, column, where):
    try:
        cur, listy = database.cursor(), []
        cur.execute(f"SELECT {column} FROM r9k {where};")
        for tp in cur.fetchall():
            listy.append(tp[0])
        cur.close()
        return listy
    except psycopg2.ProgrammingError:
        cur.close()
        return None


def get_ids(datab, rmd):
    no = "WHERE Removed"
    if rmd is None : no = ""
    elif not rmd : no = "WHERE NOT Removed"
    dalist = get_from_db(datab, "PostID", no)
    if dalist is None: return None
    return dalist


def get_row(datab, sm):
    nice = get_from_db(datab, "*", f"WHERE PostID = {sm.id}")
    if nice is None : return None
    return nice


def show_images(image1, image2):
    fig, axes = plt.subplots(nrows=1, ncols=2)
    ax = axes.ravel()
    ax[0].imshow(img_as_float(image1))
    ax[0].set_title("The image")
    ax[1].imshow(img_as_float(image2))
    ax[1].set_title("The second image")
    plt.tight_layout()
    plt.show()


# def archive(sub):


# def the_final_solution(red, sub, imger, db):

