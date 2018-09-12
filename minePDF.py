#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 14 13:35:53 2018
This script mines the pdf content and returns it as a manageable object

@author: digitalia-aj
"""
"""
input: full path to pdf file
output: 
"""

import pdfminer
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument

from pdfminer.pdfpage import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator

def startParsingPDF(fullitempath):
    # Open a PDF file.
    fp = open(fullitempath, "rb")
    print("parsing")
    # Create a PDF parser object associated with the file object.
    parser = PDFParser(fp)
    print("creating pdf object")
    # Create a PDF document object that stores the document structure.
    # Password for initialization as 2nd parameter
    document = PDFDocument(parser)
        
    # Check if the document allows text extraction. If not, abort.
    if not document.is_extractable:
        raise PDFTextExtractionNotAllowed

    # Create a PDF resource manager object that stores shared resources.
    rsrcmgr = PDFResourceManager()

    # Create a PDF device object.
    device = PDFDevice(rsrcmgr)

    # BEGIN LAYOUT ANALYSIS
    # Set parameters for analysis.
    laparams = LAParams(all_texts=True)

    # Create a PDF page aggregator object.
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)

    # Create a PDF interpreter object.
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    # loop over all pages in the document
    #pagecount = 0
    #print("test")
    #for page in PDFPage.get_pages(document):
    returnList = [document, interpreter, device]
    return returnList    
    

def getPDFPagePlainText(page, interpreter, device):
    interpreter.process_page(page)
    layout = device.get_result()
    textContent = []
    textContent = parse_obj_just_text(layout, textContent)
    return textContent    

def parse_obj_just_text(lt_objs, textContent):        
    for obj in lt_objs:        
        if isinstance(obj, pdfminer.layout.LTTextLine): #Further parse textline object            
            linetext = pdfminer.layout.LTTextLine.get_text(obj)            
            textContent.append(linetext)            
        
        elif isinstance(obj, pdfminer.layout.LTTextBoxHorizontal): #Further parse textbox objects           
            parse_obj_just_text(obj._objs, textContent)
        # if it's a container, recurse
        elif isinstance(obj, pdfminer.layout.LTFigure): #What to do with image type objects
            print("Image type item found")
            parse_obj_just_text(obj._objs, textContent)         
            
        elif isinstance(obj, pdfminer.layout.LTPage):
            print("page")
              
    return textContent


def handlePDFPages(page, interpreter, device):    
    interpreter.process_page(page)
    layout = device.get_result()
    
    textlocations = []
    textlocations = parse_obj_with_coordinates(layout, textlocations)
    return textlocations

def parse_obj_with_coordinates(lt_objs, textlocations):
    tempword = ""           
    forbiddenChars =[',','.',':','>','<','!','?','[',']','(',')','{','}','&', ' ', '  ']   
    tempWordData = []
    endY = endX = 0
    
    for obj in lt_objs:
        if isinstance(obj, pdfminer.layout.LTChar):
            
            tempChar = str(obj.get_text())
            if tempChar not in forbiddenChars:
                beginX =round(obj.x0, 2) #Gets the co-ordinates of every character
                endX = round(obj.x1, 2)
                beginY =round(obj.y0, 2)
                endY = round(obj.y1, 2)
                if tempword=="": #Word is currently blank, --> coordinates of the first character
                    tempWordData.append(beginX)
                    tempWordData.append(beginY)
                    
                tempword+=tempChar                
            else:                
                if tempWordData:
                    tempWordData.append(endX)
                    tempWordData.append(endY)
                    tempWordData.append(tempword)                    
                    textlocations.append(tempWordData)
                    tempWordData=[]
                tempword=""
        elif isinstance(obj, pdfminer.layout.LTAnno): #Annotation character found  
            if len(tempWordData)>1: #If previous tempworddata is not empty --> add ending coordinates
                tempWordData.append(endX)
                tempWordData.append(endY)
                tempWordData.append(tempword) #and add the word itself
                #print(tempWordData)
                textlocations.append(tempWordData) #Add all to textlocations list
                tempWordData=[]
                tempword = ""
        
        elif isinstance(obj, pdfminer.layout.LTTextLineHorizontal): #Further parse textline object            
            tempword=""
            parse_obj_with_coordinates(obj._objs, textlocations)
        
        elif isinstance(obj, pdfminer.layout.LTTextBoxHorizontal): #Furthher parse textbox objects
            tempword=""
            parse_obj_with_coordinates(obj._objs, textlocations)
        # if it's a container, recurse
        elif isinstance(obj, pdfminer.layout.LTFigure): #What to do with image type objects
            print("Image type item found")            
            beginX =abs(round(obj.x0, 2)) #Gets the co-ordinates of a figure
            endX = abs(round(obj.x1, 2))
            beginY =abs(round(obj.y0, 2))
            endY = abs(round(obj.y1, 2))
            tempWordData.append(beginX)
            tempWordData.append(beginY)
            tempWordData.append(endX)
            tempWordData.append(endY)
            tempWordData.append("Figure")
            textlocations.append(tempWordData)
            tempWordData=[]
            parse_obj_with_coordinates(obj._objs, textlocations)
        elif isinstance(obj, pdfminer.layout.LTPage):
            print("page")
            parse_obj_with_coordinates(obj._objs, textlocations)
     
    return textlocations
   