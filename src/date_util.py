# -*- coding: utf-8 -*-
import re

NON_ALPHA_RE = re.compile(r'\W')
# DATE_ALLSEP_RE = re.compile(r'(0[1-9]|[12][0-9]|3[01])(?:([eè]re?)|e|è)?[\/\-\. ]((0[1-9]|1[012])|(jan(vier)?)|(f[ée]v(rier)?)|(mar(s)?)|(avr(il)?)|(mai)|(jui(n)?)|(jul(liet)?)|(ao[uû]t)|(sep(tembre)?)|(oct(obre)?)|(nov(embre)?)|(d[eé]c(embre)?))[\/\-\. ](?:\d{2}){1,2}')
DATE_SLASH_RE =  re.compile(r'(?<!\d)(?:0?[1-9]|[12][0-9]|3[01])(?:([eè]re?)|e|è)?\/((0?[1-9]|1[012])|(jan(vier)?)|(f[ée]v(rier)?)|(mar(s)?)|(avr(il)?)|(mai)|(jui(n)?)|(jul(liet)?)|(ao[uû]t)|(sep(tembre)?)|(oct(obre)?)|(nov(embre)?)|(d[eé]c(embre)?))\/(?:(?:20)?\d{2}(?!\d))')
DATE_HYPHEN_RE = re.compile(r'(?<!\d)(?:0?[1-9]|[12][0-9]|3[01])(?:([eè]re?)|e|è)?\-((0?[1-9]|1[012])|(jan(vier)?)|(f[ée]v(rier)?)|(mar(s)?)|(avr(il)?)|(mai)|(jui(n)?)|(jul(liet)?)|(ao[uû]t)|(sep(tembre)?)|(oct(obre)?)|(nov(embre)?)|(d[eé]c(embre)?))\-(?:(?:20)?\d{2}(?!\d))')
DATE_POINT_RE =  re.compile(r'(?<!\d)(?:0?[1-9]|[12][0-9]|3[01])(?:([eè]re?)|e|è)?\.((0?[1-9]|1[012])|(jan(vier)?)|(f[ée]v(rier)?)|(mar(s)?)|(avr(il)?)|(mai)|(jui(n)?)|(jul(liet)?)|(ao[uû]t)|(sep(tembre)?)|(oct(obre)?)|(nov(embre)?)|(d[eé]c(embre)?))\.(?:(?:20)?\d{2}(?!\d))')
DATE_SPACE_RE =  re.compile(r'(?<!\d)(?:0?[1-9]|[12][0-9]|3[01])(?:([eè]re?)|e|è)? ((jan(vier)?)|(f[ée]v(rier)?)|(mar(s)?)|(avr(il)?)|(mai)|(jui(n)?)|(jul(liet)?)|(ao[uû]t)|(sept?(embre)?)|(oct(obre)?)|(nov(embre)?)|(d[eé]c(embre)?))\.? (?:(?:20)?\d{2}(?!\d))')
ER_RE = re.compile(r"[eérè]")



MONTH_DICT = {1:['janvier','jan'],
            2:['février','fevrier', 'fev', 'fév'],
            3:['mars', 'mar'],
            4:['avril', 'avr'],
            5:['mai'],
            6:['juin', 'jui'],
            7:['julliet', 'jul'],
            8:['août', 'aout'],
            9:['septembre', 'sep'],
            10:['octobre', 'oct'],
            11:['novembre', 'nov'],
            12:['décembre','decembre', 'dec', 'déc'],
            }

INVERT_MONTH_DICT = {}
for num in MONTH_DICT:
    names = MONTH_DICT[num]
    for name in names:
        INVERT_MONTH_DICT[name] = num


def uniform_date(date_string):
    """ Convert all form (day,month,year) to dd/MM/YYYY. 
    Return None if failed
    """
    splits = NON_ALPHA_RE.split(date_string)
    if len(splits) != 3:
        # print("Date conversion err: Must contain day, month and year. Given {}. Return None".format(date_string))
        return None
    try:
        day = ER_RE.sub("",splits[0])
        day = "{:02d}".format(int(day))
        month = splits[1]
        
        year = int(splits[2])
        if year <= 99:
            year += 2000
        if month in INVERT_MONTH_DICT:
            month = INVERT_MONTH_DICT[month]
        elif not month.isdigit():
            raise Exception
        month = "{:02d}".format(int(month))
        return "{}/{}/{}".format(day,month,year)
    except Exception:
        print("Date conversion err: Unsupport format, given {}. Return None".format(date_string))
        return None


def get_dates_in_text(text):
    """Given a text, find all date patterns
    
    Args:
    ---
        text (str): a text to look for dates
    Returns:
    ---
        list of res: (position, orginal_date, nice_form_date)
        - position: (start,stop) of orginal_date in text
        - orginal_date: date_form as found in text
        - nice_form_date: orginal_date convert to format dd/MM/YYYY
    """
    regexes = [DATE_SLASH_RE,DATE_SPACE_RE,DATE_HYPHEN_RE,DATE_POINT_RE]
    out = []
    for regex in regexes:
        result = regex.finditer(text)
        for match in result:
            value = match.group(0)
            start,end = match.span()
            # if start > 0:
            #     start+=1
            #     value=value[1:]
            nice_form = uniform_date(value)
            out.append(((start,end), value, nice_form))
    out = sorted(out, key=lambda date: date[0][0])
    return out


def test_date():
    text = """12/12/19
    Facture: 2019-10-2018
    Date de visite technique 23/01/9219
Date de visite technique 23/01/2019
25/12/19 Téléphone : 09 81 87 674
asdubatiment@hotmail.fr 
AS DU BATIMENT
Resistance=19000.00
R>111.92m19/13/2019
R111.m

35 15 15

R>111,01zm19/10/2019

qsdqdq2 19-mai-19 22
21 janv ier 212 SANS NS NS NUE N EE TETE IRC CESR 0010
CEROART 24-mai-99 SIC TK Nc Ie) ACIER TES
qsdqdq2 19-decembre-122
 janvier 2091
2e fev 1888
3è mar 18
188/225/79
Siren : 514 684 539 — TVA Int. : FR63514684539"""

    for i in get_dates_in_text(text):
        print(i)


if __name__ == "__main__":
    test_date()