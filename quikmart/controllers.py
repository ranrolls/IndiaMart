import os
import httplib
import xml.dom.minidom
from flask import Flask, request, Response
from flask import render_template, url_for, redirect, send_from_directory

from quikmart import app
import string
from settings import verbs, prep, adj

import json
import re, collections

from datetime import timedelta  
from flask import Flask, make_response, request, current_app  
from functools import update_wrapper


def crossdomain(origin=None, methods=None, headers=None, max_age=21600, attach_to_all=True, automatic_options=True):  
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator


import google

@app.route("/google")
def google():
	g = google()
	return str(g)	

# app controllers
@app.route('/')
def index():
	return render_template('index.html')

@app.route('/about')
def about():
	return render_template('about.html')

def words(text): 
	return re.findall('[a-z]+', text.lower()) 

def train(features):
    model = collections.defaultdict(lambda: 1)
    for f in features:
        model[f] += 1
    return model

NWORDS = train(words(file('train.txt').read()))
searchTerms = dict()
alphabet = 'abcdefghijklmnopqrstuvwxyz'

def edits1(word):
   splits     = [(word[:i], word[i:]) for i in range(len(word) + 1)]
   deletes    = [a + b[1:] for a, b in splits if b]
   transposes = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b)>1]
   replaces   = [a + c + b[1:] for a, b in splits for c in alphabet if b]
   inserts    = [a + c + b     for a, b in splits for c in alphabet]
   return set(deletes + transposes + replaces + inserts)

def known_edits2(word):
    return set(e2 for e1 in edits1(word) for e2 in edits1(e1) if e2 in NWORDS)

def known(words): return set(w for w in words if w in NWORDS)

def correct(word):
    candidates = known([word]) or known(edits1(word)) or known_edits2(word) or [word]
    return max(candidates, key=NWORDS.get)


import inflect
P = inflect.engine()
def getPS(s):
	if s in adj:
		return s
	if s[-1] == 's':
		return P.singular_noun(s)
	return P.plural(s)


def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
 
    # len(s1) >= len(s2)
    if len(s2) == 0:
        return len(s1)
 
    previous_row = xrange(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1 # j+1 instead of j since previous_row and current_row are one character longer
            deletions = current_row[j] + 1       # than s2
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
 
    return previous_row[-1]

@app.route("/ns", methods=['GET'])
@crossdomain(origin='*')
def search1():
	#Input query
	s = str(request.args.get("q"))
	if (len(s.strip()) == 0):
		return str(json.dumps(["No keywords", "Qualifiers", "No qualifier"]))
	s = s.lower()
	s = s.split()
	
	#Get all keys (unchecked) from the query i.e. NLP 
	uncheckedKeys = []
	flag = False
	for i in range(len(s)):
		if s[i] == "am":
			flag = True
			continue
		if flag:
			flag = False
			continue
		if correct(s[i]) in verbs or s[i] in prep or s[i] in adj or s[i] in string.digits or s[i] in verbs:
			continue
		if len(s[i]) == 1:
			continue
		uncheckedKeys.append(s[i])

	#Get Adjectives
	qualifiers = set()
	for word in s:
		if correct(word.lower()) in adj:
			qualifiers.add(correct(word).capitalize())
		if word in string.digits:
			qualifiers.add(word)

	#Gets value to dictionary
	dictValue = uncheckedKeys[:]
	dictValue.extend(list(qualifiers))
	dictValue = tuple(dictValue)
	if dictValue in searchTerms:
		return searchTerms[dictValue]

	#Initialize the variables to check for Context Recognition
	lines = [line.strip().lower() for line in open('test.txt')]
	tempLines = lines[:] # Stores the collection of terms which match word i
	
	exited = False # Did the program use context recognition
	tempSearch = ""
	if len(uncheckedKeys) > 0:
		uncheckedKeys[0] = correct(uncheckedKeys[0])
	
	#Set the value of the spell checked query in tempSearch
	for c in uncheckedKeys:
		tempSearch += c + ' '
	tempSearch = tempSearch[:-1]
	
	#Start loop for context recognition
	for word in uncheckedKeys:
		tempHelperLines = [] #Temporary array used to remove elements from tempLines
		for line in tempLines:
			if word in line and (line.startswith(word) or line[line.find(word) - 1] == ' '):
				tempHelperLines.append(line)
		if len(tempHelperLines) > 0:
			tempLines = tempHelperLines[:]
		else:  # Get the most similar string out of the queries which match the rest of the string
			min = 1000 
			minIndex = 0
			out = ""
			for c in uncheckedKeys: # out is the variable used to get the whole query string. 
				out += c + ' '
			for i in range(len(tempLines)):
				x = levenshtein(tempLines[i], out)
				if x < min:
					min = x
					minIndex = i
			keywords = [tempLines[minIndex].capitalize()] #Set keywords to the most similar string. 
			exited = True
			break
	if not exited:
		flag = False
		for i in range(len(s)): # Now for manual checking - Get everything again
			if s[i] == "am":
				flag = True
				continue
			if flag:
				flag = False
				continue
			if s[i] in verbs or s[i] in prep or s[i] in qualifiers: 
				continue
			if len(s[i]) == 1: 
				continue

			uncheckedKeys.append(s[i])
			uncheckedKeys.append(getPS(s[i])) #Add plural / singular of the noun depending on the present state.
		
		uncheckedKeys = [str(x) for x in uncheckedKeys]
		checkedKeys = [] # Checked keys are entered in this array, which are in the text file, but may contain duplicated and nulls and adjectives.
		lines = [line.strip() for line in open('test.txt')]
		for line in lines:
			flag = True
			for i in line.split():
				if i.lower() not in uncheckedKeys:
					flag = False
					break
			if flag == True:
				if line not in checkedKeys:
					checkedKeys.append(line)

		#Preprocessing for final step
		checkedKeys = [s.capitalize() for s in checkedKeys]
		
		# Remove duplicates and form final keyword array.
		finalKeys = []
		for x in checkedKeys:
			if not x in finalKeys and len(x) > 1 and x.lower() not in adj and x not in string.digits:
				finalKeys.append(x)

		keywords = finalKeys[:] # Set keywords to be the final checked keys without repetitions and nulls 
	
	# If there are no keywords, delete all qualifiers if the exists and return a practically empty array 
	if (len(keywords) == 0):
		keywords = ["No keywords"]
		qualifiers = ["No qualifiers"]
	else:
		if levenshtein(max(keywords, key=len).lower(), tempSearch.lower()) > (max(len(max(keywords, key=len)), len(tempSearch)) + 1) / 2:
			keywords = ["No keywords"]
			qualifiers = ["No qualifiers"]
	if (len(qualifiers) == 0):
		qualifiers = ["No qualifiers"]
	keywords.append("Qualifiers") # Else separate the Keywords and Qualifiers by "Qualifiers" and output : To be taken in by the program
	keywords.extend(list(qualifiers))
	searchTerms[dictValue] = str(json.dumps(keywords))
	return str(json.dumps(keywords))
				
'''
@app.route("/search", methods=['GET'])
@crossdomain(origin='*')
def search():
	s = request.args.get("q")
	s = s.lower()
	tempSearch = s[:]
	s = s.split()
	final = []

	for i in range(len(s)):
	    if s[i] in verbs or s[i] in prep:
	        continue
	    if len(s[i]) == 1:
	        continue
	    final.append(s[i])
	    final.append(getPS(s[i]))
	final = [str(x) for x in final]
	final2 = []
	lines = [line.strip() for line in open('test.txt')]
	for line in lines:
		flag = True
		for i in line.split():
			if i.lower() not in final:
				flag = False
				break
		if flag == True:
			if line not in final2:
				final2.append(line)
	
	final2 = [s.capitalize() for s in final2]
	final1 = []
	for x in final2:
		if not x in final1 and len(x) > 1 and x not in adj:
			final1.append(x)

	

	qual = set()
	for a in final:
	    flag = False
	    for b in final1:
	        if a.lower() in b.lower():
	            flag = False
	    if flag == False and a.lower() in adj:
	        qual.add(a.capitalize())

	final1.sort(lambda x, y : cmp(len(y), len(x)))
	final1 = list(set(final1).difference(qual))
	keywords = []
	for k in final1:
		if k.lower() in tempSearch or k.lower() in getPS(tempSearch):
			keywords = [k.capitalize()]
			break

	maxKeyword = ""
	for key in final1:
		if key.lower() in tempSearch:
			if len(key) > len(maxKeyword):
				maxKeyword = key
	
	keywords = []
	for x in final1:
		if x.lower() not in maxKeyword.lower():
			keywords.append(x.capitalize())		
	keywords = final1[:]

	if (len(keywords) == 0):
		keywords = ["No keywords"]
		qual = ["No qualifiers"]
	if (len(qual) == 0):
		qual = ["No qualifiers"]
	keywords.append("Qualifiers")
	keywords.extend(list(qual))
	return str(json.dumps(keywords))
'''

# special file handlers
@app.route('/favicon.ico')
def favicon():
	return send_from_directory(os.path.join(app.root_path, 'static'), 'img/favicon.ico')


# error handlers
@app.errorhandler(404)
def page_not_found(e):
	return render_template('404.html'), 404
