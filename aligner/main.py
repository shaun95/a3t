#!/usr/bin/env python

""" 
This is an example of how to use the force aligner to align English text to audio.
Once you can run this script successfully, you can take a look of `espnet2/bin/align_english.py` to see how to do multiprocess alignment with a wav.scp file and a text file.

    Usage:
      python main.py
"""

import os
import sys
from tqdm import tqdm
import multiprocessing as mp
from espnet2.text.phoneme_tokenizer import G2p_en

g2p_tokenzier=G2p_en(no_space=True)
PATH2thisproject = os.path.dirname(os.path.abspath(__file__))+'/..'
PHONEME = f'{PATH2thisproject}/tools/english2phoneme/phoneme'
MODEL_DIR = f'{PATH2thisproject}/tools/alignment/aligner/english'
HVITE = f'{PATH2thisproject}/tools/HTKTools/HVite'
HCOPY = f'{PATH2thisproject}/tools/HTKTools/HCopy'

def prep_txt(line, tmpbase, dictfile):
 
    words = []

    line = line.strip()
    for pun in [',', '.', ':', ';', '!', '?', '"', '(', ')', '--', '---']:
        line = line.replace(pun, ' ')
    for wrd in line.split():
        if (wrd[-1] == '-'):
            wrd = wrd[:-1]
        if len(wrd)>0 and (wrd[0] == "'"):
            wrd = wrd[1:]
        if wrd:
            words.append(wrd)

    ds = set([])
    with open(dictfile, 'r') as fid:
        for line in fid:
            ds.add(line.split()[0])

    unk_words = set([])
    with open(tmpbase + '.txt', 'w') as fwid:
        for wrd in words:
            if (wrd.upper() not in ds):
                unk_words.add(wrd.upper())
            fwid.write(wrd + ' ')
        fwid.write('\n')

    #generate pronounciations for unknows words using 'letter to sound'
    with open(tmpbase + '_unk.words', 'w') as fwid:
        for unk in unk_words:
            fwid.write(unk + '\n')
    try:
        os.system(PHONEME + ' ' + tmpbase + '_unk.words' + ' ' + tmpbase + '_unk.phons')
    except:
        print('english2phoneme error!')
        sys.exit(1)

    #add unknown words to the standard dictionary, generate a tmp dictionary for alignment 
    fw = open(tmpbase + '.dict', 'w')
    with open(dictfile, 'r') as fid:
        for line in fid:
            fw.write(line)
    f = open(tmpbase + '_unk.words', 'r')
    lines1 = f.readlines()
    f.close()
    f = open(tmpbase + '_unk.phons', 'r')
    lines2 = f.readlines()
    f.close()
    for i in range(len(lines1)):
        wrd = lines1[i].replace('\n', '')
        phons = lines2[i].replace('\n', '').replace(' ', '')
        seq = []
        j = 0
        while (j < len(phons)):
            if (phons[j] > 'Z'):
                if (phons[j] == 'j'):
                    seq.append('JH')
                elif (phons[j] == 'h'):
                    seq.append('HH')
                else:
                    seq.append(phons[j].upper())
                j += 1
            else:
                p = phons[j:j+2]
                if (p == 'WH'):
                    seq.append('W')
                elif (p in ['TH', 'SH', 'HH', 'DH', 'CH', 'ZH', 'NG']):
                    seq.append(p)
                elif (p == 'AX'):
                    seq.append('AH0')
                else:
                    seq.append(p + '1')
                j += 2

        fw.write(wrd + ' ')
        for s in seq:
            fw.write(' ' + s)
        fw.write('\n')
    fw.close()

def prep_mlf(txt, tmpbase):

    with open(tmpbase + '.mlf', 'w') as fwid:
        fwid.write('#!MLF!#\n')
        fwid.write('"' + tmpbase + '.lab"\n')
        fwid.write('sp\n')
        wrds = txt.split()
        for wrd in wrds:
            fwid.write(wrd.upper() + '\n')
            fwid.write('sp\n')
        fwid.write('.\n')

def alignment(wav_path, text_string):
    tmpbase = '/tmp/' + os.environ['USER'] + '_' + str(os.getpid())

    #prepare wav and trs files
    try:
        os.system('sox ' + wav_path + ' -r 16000 ' + tmpbase + '.wav remix -')
    except:
        print('sox error!')
        return None
    
    #prepare clean_transcript file
    try:
        prep_txt(text_string, tmpbase, MODEL_DIR + '/dict')
    except:
        print(wav_path)
        print('prep_txt error!')
        return None

    #prepare mlf file
    try:
        with open(tmpbase + '.txt', 'r') as fid:
            txt = fid.readline()
        prep_mlf(txt, tmpbase)
    except:
        print(wav_path)
        print('prep_mlf error!')
        return None

    #prepare scp
    try:
        os.system(HCOPY + ' -C ' + MODEL_DIR + '/16000/config ' + tmpbase + '.wav' + ' ' + tmpbase + '.plp')
    except:
        print(wav_path)
        print('HCopy error!')
        return None

    #run alignment
    try:
        os.system(HVITE + ' -a -m -t 10000.0 10000.0 100000.0 -I ' + tmpbase + '.mlf -H ' + MODEL_DIR + '/16000/macros -H ' + MODEL_DIR + '/16000/hmmdefs -i ' + tmpbase +  '.aligned '  + tmpbase + '.dict ' + MODEL_DIR + '/monophones ' + tmpbase + '.plp 2>&1 > /dev/null') 
    except:
        print(wav_path)
        print('HVite error!')
        return None

    with open(tmpbase + '.txt', 'r') as fid:
        words = fid.readline().strip().split()
    words = txt.strip().split()
    words.reverse()

    with open(tmpbase + '.aligned', 'r') as fid:
        lines = fid.readlines()
    i = 2
    times2 = []
    word2phns = {}
    current_word = ''
    index = 0
    while (i < len(lines)):
        splited_line = lines[i].strip().split()
        if (len(splited_line) >= 4) and (splited_line[0] != splited_line[1]):
            phn = splited_line[2]
            pst = (int(splited_line[0])/1000+125)/10000
            pen = (int(splited_line[1])/1000+125)/10000
            times2.append([phn, pst, pen])
            # splited_line[-1]!='sp'
            if len(splited_line)==5:
                current_word = str(index)+'_'+splited_line[-1]
                word2phns[current_word] = phn
                index+=1
            elif len(splited_line)==4:
                word2phns[current_word] += ' '+phn 
        i+=1
    return times2, word2phns

wavfile = "1089-134686-0000.flac"
trsfile = "he hoped there would be stew for dinner turnips and carrots and bruised potatoes and fat mutton pieces to be ladled out in thick peppered flour fattened sauce"
phn2timestamp, word2phns = alignment(wavfile, trsfile)

print("The phoneme to timestamp mapping is:")
print(phn2timestamp)

print("The word to phoneme mapping is:")
print(word2phns)