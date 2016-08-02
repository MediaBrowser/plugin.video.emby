# -*- coding: utf-8 -*-

#################################################################################################

def cleanPassword(password):

    password = password or ""

    password = password.replace("&", '&amp;')
    password = password.replace("/", '&#092;')
    password = password.replace("!", '&#33;')
    password = password.replace("$", '&#036;')
    password = password.replace("\"", '&quot;')
    password = password.replace("<", '&lt;')
    password = password.replace(">", '&gt;')
    password = password.replace("'", '&#39;')

    return password