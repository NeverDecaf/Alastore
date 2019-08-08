import winshell, re, os

HASYEAR = re.compile('.*\d\d\d\d')
def mkDir(dname):
    if not os.path.isdir(dname):
        os.makedirs(dname)
        return True
    return False

def mklinkW(src,dst):
    src = os.path.join(src,os.path.basename(dst)+'.lnk')
    with winshell.shortcut(src) as link:
        link.path=dst
    
def retro_link(src):
    src = os.path.abspath(src)
    years = []
    for f in os.listdir(src):
        if HASYEAR.match(f) and os.path.isdir(os.path.join(src,f)):
            years.append(os.path.join(src,f))
    seasons=[]
    for year in years:
        for f in os.listdir(year):
            if HASYEAR.match(f) and os.path.isdir(os.path.join(year,f)):
                seasons.append(os.path.join(year,f))
    series=[]
    for season in seasons:
        for f in os.listdir(season):
            series.append(os.path.join(season,f))
    mkDir(os.path.join(src,'All_Series'))
    print('creating shortcuts for %s series'%len(series))
    for s in series:
        mklinkW(os.path.join(src,'All_Series'),s)
if __name__=='__main__':
    retro_link('.')
