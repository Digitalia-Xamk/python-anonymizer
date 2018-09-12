#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 22 11:44:09 2017

@author: digitalia-aj
"""
import multiprocessing
from multiprocessing import Pool
import sys
import csv
import os
import time
import subprocess
from pdfminer.pdfpage import PDFPage
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from PyPDF2 import PdfFileReader, PdfFileWriter
import io
import textract
import chardet
import minePDF #Own developed Python file, included in commit

"""
*************************************************************
Select variables according to environment
*************************************************************
"""
hideImages = False #If this is set to true, tries to mask also items recognized as images
useFinnishNameData = True #Use or not use Finnish name data files downloaded from xx
useNERRecognition = True #Tries to use NER to detect personal information
cleanTempFiles = True #Cleans temporary PDF files if requested
redoOCRing = True #Re OCR the masked png files and combines the result into final pdf file.
useAdditionalData = False #Uses additional-data.csv file from run dir if true

"""
*************************************************************
Filename holders
*************************************************************
"""
finerPath = "/home/user/finer/"
namedataPath = "/home/user/nimidata/"
"""Contains sukunimitilasto-2018-03-05.csv and etunimitilasto-2018-03-05.csv
not included in commit, get from opendata.fi"""

tessdatadir = '/usr/local/share/tessdata' #Tesseract data directory
gspath = '/home/user/ghostscript/gs-922' #Path to ghostscript

def printmessage(message):
    #printmessage(time.strftime("%H:%M:%S", time.localtime()))    
    try:
        message = time.strftime("%H:%M:%S", time.localtime())+">"+str(message)
        print(message)
        logfile.write(message+"\n")
    except OSError:
        pass
    return

def docmd(cmd):
    global convertedFilesCount
    printmessage("manipulating "+str(cmd))
    convertprocess = subprocess.Popen(cmd)
    convertprocess.communicate()
    return


def getContentEncoding(filename):
    encoding = 'utf-8' #utf-8 as a default encoding
    content = textract.process(filename)    
    chardetResult = chardet.detect(content)
    
    #newencoding = ""
    for key, value in chardetResult.items():                                    
        if str(key)=="encoding":
            encoding = value
    #Content should be decoded correctly
    content = textract.process(fullitempath).decode(encoding)  
    
    return content, encoding


def langDetect(content):
    global languageDetected
    printmessage("Detecting languages")    
    langDict = {}        
    try:
        languages = Detector(content).languages
        for x in range(0, len(languages)):
            code = languages[x].code
            if code != 'un':
                confidence = languages[x].confidence
                langDict[code]=confidence
                
    except Exception as e:
        printmessage("Language detection error -->"+str(e))          
        languages = langid.classify(content)
        #printmessage(languages)
        code = languages[0]
        confidence = abs(languages[1])
        if confidence > 99:
            confidence = 99
        else:
            confidence = round(confidence, 0)
        langDict[code]=confidence
    printmessage(langDict)        
    return langDict


def csvReader(file):
    reader = csv.reader(open(file, encoding='utf-8'), delimiter=",")    
    result = {}
    i = 0        
    for row in reader:   
        tempword = row[0] #Name is the first (and only) element of csv row        
        result[i] = tempword                
        i += 1      
    return result

def removeFile(filename): #actual method that remove files
    try:        
        printmessage("Trying to delete file -->{}".format(filename))
        os.remove(filename)
    except OSError:
        pass
    return

def anonymizePDFPage(page):    
    if textlocations!=[]:
        mask = io.BytesIO()
        # create a new PDF with Reportlab
        can = canvas.Canvas(mask)
        
        i = 0
        """
        Place "defaultmask" with a little green dot on every page, otherwise the mask does not exist
        and the execution will crash on combine phase
        """
        can.setFillColor(colors.green)
        rectX = 0 #First value is always the X-coordinate
        rectY = 0 #Second value is always the Y-coordinate
        width = 1 #third is the last items X1 coordinate
        height = 1 #Fourth is the last items Y1 coodinate, -2 to shrink the box a bit                        
        can.rect(rectX, rectY, width, height, stroke=0, fill=1)        
        
        """The actual place that does the masking      
        """
        while i < len(textlocations):
            theWord = textlocations[i][4] #4 should be always the word
            wordMasked = False
            #printmessage(theWord)
            if useNERRecognition and wordMasked==False:
                if theWord in nersInText:
                    printmessage("NER person found")
                    can.setFillColor(colors.red)
                    rectX = textlocations[i][0] #First value is always the X-coordinate
                    rectY = textlocations[i][1] #Second value is always the Y-coordinate
                    width = textlocations[i][2]-rectX #third is the last items X1 coordinate
                    height = textlocations[i][3]-rectY-2 #Fourth is the last items Y1 coodinate, -2 to shrink the box a bit                        
                    can.rect(rectX, rectY, width, height, stroke=0, fill=1)
                    wordMasked = True
            
            if useFinnishNameData and wordMasked==False:
                if theWord in familynameData.values() or theWord in firstnameData.values():
                    printmessage("Family or person name found")
                    can.setFillColor(colors.black)
                    rectX = textlocations[i][0] #First value is always the X-coordinate
                    rectY = textlocations[i][1] #Second value is always the Y-coordinate
                    width = textlocations[i][2]-rectX #third is the last items X1 coordinate
                    height = textlocations[i][3]-rectY-2 #Fourth is the last items Y1 coodinate, -2 to shrink the box a bit                        
                    can.rect(rectX, rectY, width, height, stroke=0, fill=1)
                    wordMasked = True            
           
            
            if useAdditionalData and wordMasked==False: #Just testing the effect
                if theWord in additionalData.values(): #or theWord=="Figure":
                    #printmessage("FOUND!")
                    can.setFillColor(colors.blue)
                    rectX = textlocations[i][0] #First value is always the X-coordinate
                    rectY = textlocations[i][1] #Second value is always the Y-coordinate
                    width = textlocations[i][2]-rectX #third is the last items X1 coordinate
                    height = textlocations[i][3]-rectY-2 #Fourth is the last items Y1 coodinate, -2 to shrink the box a bit                        
                    can.rect(rectX, rectY, width, height, stroke=0, fill=1)
                    wordMasked=True
            i+=1
       
        can.save()
        
        #move to the beginning of the StringIO buffer
        mask.seek(0)
        maskLayer = PdfFileReader(mask)
        # read your existing PDF
        existing_pdf = PdfFileReader(open(fullitempath, "rb"))
        output = PdfFileWriter()
        # add the "watermark" (which is the new pdf) on the existing page
        page = existing_pdf.getPage(pagecount)
        page.mergePage(maskLayer.getPage(0))                    
        output.addPage(page)
        # finally, write "output" to a real file
        outputpdf = begin+"_"+str(pagecount)+"."+str(end)
        outputpng = begin+"_"+str(pagecount)+".png"
        outputpdf = os.path.join(root, outputpdf)
        outputpng = os.path.join(root, outputpng)
        outputPDFFiles.append(outputpdf) #Adds every created pdf page to list
        
        
        outputStream = open(outputpdf, "wb")
        output.write(outputStream)
        outputStream.close()
        if redoOCRing:
            if os.path.isfile(outputpdf): #File written succesfully
                """Use imagemagick convert to convert it to png, after which it should be re ocred """
                topngcmd = ['convert', '-alpha', 'off','-density', '600', '-quality', '100', outputpdf, '-resize', '25%', outputpng]
                docmd(topngcmd)
                outputPNGFiles.append(outputpng) #Adds every created png page to list
        
        return 1

def handlePDFPagesResult(result, original):           
    printmessage("Got a result from handlepdfpages")
    if '1' in str(result):
        printmessage(result)
    return
    

"""THIS IS THE MAIN APP"""
starttime = time.time() 
logfile = open('anonymizer.log', 'w')
cpucount = multiprocessing.cpu_count()
pool = Pool(cpucount)
printmessage ("Available CPUs: {}, but this version does not utilize those. Contact Digitalia if you wish to use them all. Or do it yourself ;)".format(cpucount))
printmessage ("PYTHON VERSION: {}, all above 3 will be fine ".format(sys.version_info))
printmessage ("Script is run in dir: "+str(os.path.dirname(os.path.abspath(__file__))))

walk_dir = os.getcwd()
originalFiles = []

"""
Loads finnish namedata files if useFinnishNameData = True
Currently only detects baseforms as they are in familynames and firstnames data
"""
if useFinnishNameData:    
    familynames = namedataPath+"sukunimitilasto-2018-03-05-vrk.csv"
    firstnames = namedataPath+"etunimitilasto-2018-03-05-vrk.csv"
    familynameData = csvReader(familynames)
    firstnameData = csvReader(firstnames)
   
if useAdditionalData:
    additionalDataPath = os.path.join(walk_dir, "additional-words.csv")
    if os.path.isfile(additionalDataPath):
        additionalData = csvReader(additionalDataPath)

if useNERRecognition:
    from polyglot.detect import Detector
    from polyglot.text import Text
    import langid

for root, dirs, items in os.walk(walk_dir):    
    for item in items:
        templist = []
        fullitempath = os.path.join(root, item)   
        begin, end = os.path.splitext(item)
        end = str(end).lstrip('.')
        printmessage(end)
        if end =='pdf':
            originalFiles.append(fullitempath)           
            content, encoding = getContentEncoding(fullitempath)
            printmessage(len(content))
            if len(content)<2 or content==" " or content=="":
                printmessage("There is no text content in the submitted file")
                printmessage("Please use some ocr software before submitting a file")
                printmessage("Later on we will add a functionality to ocr things automatically")
            else:
                printmessage("Content = {}".format(content))
                printmessage("Encoding = {}".format(encoding))
                """
                Before parsing the pdf structure, let's ner the content if requested
                """
                if useNERRecognition:
                    languages = langDetect(content)                
                    sortedLangDict =  sorted(languages.items(), key=lambda i:i[1], reverse=True)
                    lang, conf = sortedLangDict[0]
                    printmessage("{} {}".format(lang, conf))                
                    content = Text(content, hint_language_code=lang)
                        
                    ners = content.entities
                    nersInText = []
                    printmessage("NERS = {}".format(ners))
                    for onener in ners:
                        if onener.tag == 'I-PER':
                            for name in onener:
                                #printmessage(name)
                                """Add value to storage"""
                                nersInText.append(name)
                        
                encodingstr = "encoding='"+str(encoding)+"'"
                pdfMinerData = minePDF.startParsingPDF(fullitempath) #pdfMinerData = [document, interpreter, device]
                printmessage("pdf document parsed, length of return string is {}".format(len(pdfMinerData)))
                printmessage(pdfMinerData)
                if len(pdfMinerData)==3: #See above [document, interpreter, device]
                    pagecount = 0                    
                    """
                    Define lists for storing output pdf and png filenames
                    """
                    outputPDFFiles = []
                    outputPNGFiles = []
                    for page in PDFPage.create_pages(pdfMinerData[0]):                        
                        textlocations = minePDF.handlePDFPages(page, pdfMinerData[1], pdfMinerData[2])                        
                        #Does anonymization and ads pages to above lists
                        anonymizePDFPage(page)
                        pagecount+=1                   
                       
                    if redoOCRing:
                        handledPDFFiles = []
                        printmessage("Requested reOCR of files {}".format(outputPNGFiles))
                        for file in outputPNGFiles:
                            ocroutputfile = str(file)+"-OCRed"
                            ocrcmd = ['tesseract', '--psm', '12', file, ocroutputfile, 'pdf']
                            docmd(ocrcmd)
                            ocroutputfile = str(ocroutputfile)+".pdf"
                            if os.path.isfile(ocroutputfile):
                                handledPDFFiles.append(ocroutputfile)
                                if cleanTempFiles:
                                    removeFile(file)    #Thus reocred, we don't need the png files anymore
                        finalFile = "-o"+str(fullitempath)+"-Anonymized-OCRd.pdf"
                    else:
                        handledPDFFiles = []
                        finalFile = "-o"+str(fullitempath)+"-Anonymized.pdf"
                        for file in outputPDFFiles:
                            handledPDFFiles.append(file)
                    
                    #Finally combine the created pdf files                                
                    printmessage(handledPDFFiles)
                    
                    gscmd =[gspath, '-dPDFA=3',
                    '-dBATCH', '-dNOPAUSE', '-dNOOUTERSAVE', '-dNOSAFER', '-r72', '-dPDFSETTINGS=/screen',
                    '-dPDFACompatibilityPolicy=1', '-dAutoFilterColorImages=false', '-dColorImageFilter=/FlateEncode',
                    '-dAutoFilterGrayImages=false', '-dGrayImageFilter=/FlateEncode', '-dMonoImageFilter=/FlateEncode',
                    '-dEmbedAllFonts=true', '-dCompressFronts=true', '-dNOTRANSPARENCY',
                    '-sDEVICE=pdfwrite', finalFile]
        
                    for pdffile in handledPDFFiles:
                        gscmd.append(pdffile)
             
                    printmessage(gscmd)
                    docmd(gscmd)
                    finalFile = str(fullitempath)+"-OCRED.pdf"
                    
                    if cleanTempFiles:
                        if os.path.isfile(finalFile): #Combined file exists, can remove the individual ones
                            for file in handledPDFFiles:
                                removeFile(file)
                        printmessage("Requested removal of all temporary files {}".format(outputPDFFiles))
                        for file in outputPDFFiles:
                            removeFile(file)
                        for file in handledPDFFiles:
                            removeFile(file)
                else:
                    printmessage("PDF miner failed to extract required data, cannot continue")
                
                
                
                
                                
               
                        
                    
