import os
import sys
import re
import pickle

this_dir = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = '/'.join(this_dir.split('/')[:-2])
if PROJECT_DIR not in sys.path:
    sys.path.insert(1, PROJECT_DIR)

from src.utils import remove_accent


f = open(PROJECT_DIR + '/src/basedata/codepostal_ville_dict.pkl', 'rb')
CP_VILLE_DICT = pickle.load(f)  # d[cp] = [(nom_postal,nom_complet)]
f.close()

RE_CODEPOSTAL = re.compile(r"[ ,](\d{2}[ -]?\d{3}?(?!\d))")
VILLE_CLEAN_RE = re.compile(r"(\d+|-|'|ste?(?!\w)|sainte?(?!\w))")  # to be improve
MULTISPACE_RE = re.compile(r"\s+")



def _uniform_city_name(txt):
    """
    txt = supp_accent(txt.lower())\n
    txt = VILLE_CLEAN_RE.sub(" ",txt)\n
    txt = MULTISPACE_RE.sub(" ",txt)
    """
    txt = remove_accent(txt.lower())
    txt = VILLE_CLEAN_RE.sub(" ",txt)
    txt = MULTISPACE_RE.sub(" ",txt)
    return txt.strip()


def find_codepostal(txt):
    """ Find codepostal and its city in a text.

    Returns:
    ---
        List[Tuple]: [(cp,ville)]
    """
    found = []
    txt = txt.replace("\n"," ")
    txt = MULTISPACE_RE.sub(" ",txt)
    matches = RE_CODEPOSTAL.finditer(txt) 
    for match in matches:
        cp = match.group(0).strip()
        if cp in CP_VILLE_DICT:  
            start = match.span()[1]
            tail = txt[start:]
            tail = _uniform_city_name(tail)
            for ville,nom_complet in CP_VILLE_DICT[cp]:
                if _uniform_city_name(ville) in tail:
                    found.append((cp,nom_complet))
                    break
    return found


if __name__ == "__main__":
    text = "192 RUE DE DANTZIG, 75015 PARIS QSDKJ "
    print(find_codepostal(text))