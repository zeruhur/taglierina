import random
from textwrap import wrap

book = "I_misteri_della_jungla_nera.txt"
output = "salgari1_cutup.txt"

# open the text file
text_file = open(book)
 
#read whole file to a string
data = text_file.read()

#close file
text_file.close()

# number of characters to cut-up
n_char = 40

# cut all the text in chunks
cutup = wrap(data, n_char)

# shuffle of the chunks randomly
random.shuffle(cutup)

# select 500 random lines
cutup_sel = random.sample(cutup, 500)

# create output text file
f = open(output,"w+")

counter = 0 #line counter
excerpt_n = 1 #excerpt counter

f.write(f"{excerpt_n}\n") # write first excerpt number

# iterates in the cutup selection: every five lines add the new excerpt number and a blank line until the 100th excerpt
for i in cutup_sel:
    f.write(f"{i}\n")
    counter += 1
    if counter == 5:
        if excerpt_n < 100:
            excerpt_n+=1
            f.write("\n"+str(excerpt_n)+"\n")
        counter = 0

f.close() #save the file