from funcs import *

if __name__ == "__main__":
    conf = get_ini('info.ini')
    r, sr = reddit_session(conf)
    sm = r.submission(id='a9x8j8')
    get_attributes(sm)
    """
    imgur = imgur_session(conf)
    create_image_path()
    for sumi in sr.stream.submissions(pause_after=-1):
        if sumi is None: break
        if sumi.domain == "i.redd.it" or sumi.domain == "imgur.com" or sumi.domain == "i.imgur.com":
            print(sumi.id)
            save_image(sumi, imgur)
            if find_image(sumi) is not None:
                print("found it")
            else:
                print("shit")
"""