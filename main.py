# import multiprocessing as mp
from repy.funcs import *

if __name__ == "__main__":
    conf = get_ini('info.ini')
    r, sr = reddit_session(conf)
    db = db_session(conf)
    img = imgur_session(conf)
    dirlist = create_image_path()
    isempty, fsm = new_table(db)
    if isempty: archive_to_db(db, r, sr)
    smlist = db_to_ram(r, img, db, "")
    compare_lists(archive(r, sr, id_to_time(fsm[0], r)), smlist, db, img)

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
