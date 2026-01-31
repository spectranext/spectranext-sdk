#!/usr/bin/env python3
"""
pymakebas - convert a text file containing a speccy Basic program
           into an actual program file loadable on a speccy.

Public domain by Russell Marks, 1998.
Converted to Python while maintaining exact interface compatibility.
"""

import sys
import os
import struct
import math
import getopt
from typing import List, Tuple, Optional

DEFAULT_OUTPUT = "out.tap"

REM_TOKEN_NUM = 234
BIN_TOKEN_NUM = 196
VAL_TOKEN_NUM = 176
VALSTR_TOKEN_NUM = 174
DEFFN_TOKEN_NUM = 206

# tokens are stored (and looked for) in reverse speccy-char-set order,
# to avoid def fn/fn and go to/to screwups. There are two entries for
# each token - this is to allow for things like "go to" which can
# actually be entered (thank ghod) as "goto". The one extension to
# this I've made is that randomize can be entered with -ize or -ise.
#
# One exception to the above - VAL/VAL$ positions are flipped here
# so that we do VAL$ first, and swapped after tokenising.
tokens = [
    ("copy", ""),
    ("return", ""),
    ("clear", ""),
    ("draw", ""),
    ("cls", ""),
    ("if", ""),
    ("randomize", "randomise"),
    ("save", ""),
    ("run", ""),
    ("plot", ""),
    ("print", ""),
    ("poke", ""),
    ("next", ""),
    ("pause", ""),
    ("let", ""),
    ("list", ""),
    ("load", ""),
    ("input", ""),
    ("go sub", "gosub"),
    ("go to", "goto"),
    ("for", ""),
    ("rem", ""),
    ("dim", ""),
    ("continue", ""),
    ("border", ""),
    ("new", ""),
    ("restore", ""),
    ("data", ""),
    ("read", ""),
    ("stop", ""),
    ("llist", ""),
    ("lprint", ""),
    ("out", ""),
    ("over", ""),
    ("inverse", ""),
    ("bright", ""),
    ("flash", ""),
    ("paper", ""),
    ("ink", ""),
    ("circle", ""),
    ("beep", ""),
    ("verify", ""),
    ("merge", ""),
    ("close #", "close#"),
    ("open #", "open#"),
    ("erase", ""),
    ("move", ""),
    ("format", ""),
    ("cat", ""),
    ("def fn", "deffn"),
    ("step", ""),
    ("to", ""),
    ("then", ""),
    ("line", ""),
    ("<>", ""),
    (">=", ""),
    ("<=", ""),
    ("and", ""),
    ("or", ""),
    ("bin", ""),
    ("not", ""),
    ("chr$", ""),
    ("str$", ""),
    ("usr", ""),
    ("in", ""),
    ("peek", ""),
    ("abs", ""),
    ("sgn", ""),
    ("sqr", ""),
    ("int", ""),
    ("exp", ""),
    ("ln", ""),
    ("atn", ""),
    ("acs", ""),
    ("asn", ""),
    ("tan", ""),
    ("cos", ""),
    ("sin", ""),
    ("len", ""),
    ("val$", ""),
    ("code", ""),
    ("val", ""),
    ("tab", ""),
    ("at", ""),
    ("attr", ""),
    ("screen$", ""),
    ("point", ""),
    ("fn", ""),
    ("pi", ""),
    ("inkey$", ""),
    ("rnd", ""),
    ("play", ""),
    ("spectrum", ""),
]

MAX_LABELS = 2000
MAX_LABEL_LEN = 16
MAX_LINE_NUMBER_LEN = 4  # 9999 is the longest (4 chars).

# Buffer sizes - using larger non-MSDOS sizes
FILEBUF_SIZE = 49152
BUF_SIZE = 8 * 49152
OUTBUF_SIZE = 49152


class Node:
    """Linked list node for tracking line numbers"""
    def __init__(self, number: int):
        self.number = number
        self.next: Optional['Node'] = None


class OutputFormat:
    RAW = 0
    TAP = 1
    PLUS3DOS = 2


def dbl2spec(num: float) -> Tuple[bool, int, int]:
    """
    Converts a double to an inline-basic-style speccy FP number.
    
    Returns: (success, exp, man)
    - success: True if ok, False if exponent too big
    - exp: exponent byte
    - man: 4-byte mantissa as unsigned long (big-endian format)
    """
    # check for small integers
    if num == int(num) and -65535.0 <= num <= 65535.0:
        tmp = int(abs(num))
        exp = 0
        man = ((tmp % 256) << 16) | ((tmp >> 8) << 8)
    else:
        # It appears that the sign bit is always left as 0 when floating-point
        # numbers are embedded in programs, and the speccy appears to use the
        # '-' character to determine negativity - tests confirm this.
        # As such, we *completely ignore* the sign of the number.
        num = abs(num)
        
        # binary standard form goes from 0.50000... to 0.9999...(dec)
        exp = 0
        while num >= 1.0:
            num /= 2.0
            exp += 1
        
        while num < 0.5:
            num *= 2.0
            exp -= 1
        
        # check the range of exp... -128 <= exp <= 127
        if exp < -128 or exp > 127:
            return (False, 0, 0)
        
        exp = 128 + exp
        
        # roll the bits off the mantissa
        num *= 2.0  # make it so that the 0.5ths bit is the integer part
        
        man = 0
        for f in range(32):
            man <<= 1
            man |= int(num)
            num -= int(num)
            num *= 2.0
        
        # round up if needed
        if int(num) and man != 0xFFFFFFFF:
            man += 1
        
        # zero out the top bit
        man &= 0x7FFFFFFF
    
    return (True, exp, man)


def grok_hex(ptr: str, textlinenum: int) -> Tuple[int, str]:
    """Parse hexadecimal number starting with 0x"""
    hexits = "0123456789abcdefABCDEF"
    v = 0
    
    if len(ptr) < 2 or ptr[:2] != "0x":
        print(f"line {textlinenum}: bad BIN 0x... number", file=sys.stderr)
        sys.exit(1)
    
    ptr = ptr[2:]
    if not ptr or ptr[0] not in hexits:
        print(f"line {textlinenum}: bad BIN 0x... number", file=sys.stderr)
        sys.exit(1)
    
    i = 0
    while i < len(ptr) and ptr[i] in hexits:
        n = hexits.index(ptr[i])
        if n > 15:
            n -= 6
        v = v * 16 + n
        i += 1
    
    return (v, ptr[i:])


def grok_binary(ptr: str, textlinenum: int) -> Tuple[int, str]:
    """Parse binary number"""
    ptr = ptr.lstrip()
    
    if not ptr or (ptr[0] != '0' and ptr[0] != '1'):
        print(f"line {textlinenum}: bad BIN number", file=sys.stderr)
        sys.exit(1)
    
    if len(ptr) > 1 and (ptr[1] == 'x' or ptr[1] == 'X'):
        return grok_hex(ptr, textlinenum)
    
    v = 0
    i = 0
    while i < len(ptr) and (ptr[i] == '0' or ptr[i] == '1'):
        v *= 2
        v += ord(ptr[i]) - ord('0')
        i += 1
    
    return (v, ptr[i:])


class QuoteTokList:
    """Linked list for tracking line numbers that need tokenization within quotes"""
    def __init__(self):
        self.head: Optional[Node] = None
        self.curr: Optional[Node] = None
    
    def add_no_dupes(self, word: str) -> Node:
        """Add line number to list if not already present"""
        num = int(word)
        tmp = self.head
        
        while tmp:
            if tmp.number == num:
                return tmp  # reject duplicate line number
            tmp = tmp.next
        
        ptr = Node(num)
        ptr.next = None
        
        if self.head:
            self.curr.next = ptr
        else:
            self.head = ptr
        self.curr = ptr
        
        return ptr
    
    def search(self, current_line_number: int) -> bool:
        """Search for line number in list"""
        ptr = self.head
        while ptr:
            if current_line_number == ptr.number:
                return True
            ptr = ptr.next
        return False
    
    def free(self):
        """Free all nodes"""
        ptr = self.head
        while ptr:
            tmp = ptr.next
            ptr = None
            ptr = tmp
        self.head = None
        self.curr = None


def is_number(string: str) -> bool:
    """Return True if string is a valid number, False otherwise - matches C version"""
    try:
        end_idx = 0
        # Skip leading whitespace
        while end_idx < len(string) and string[end_idx].isspace():
            end_idx += 1
        if end_idx >= len(string):
            return False
        
        # Try to parse as integer
        val = int(string[end_idx:])
        # Check remaining characters are only whitespace
        remaining = string[end_idx + len(str(val)):]
        for c in remaining:
            if not c.isspace():
                return False
        return True
    except ValueError:
        return False


def grok_block(ptr: str, textlinenum: int) -> int:
    """Parse block graphics escape sequence"""
    lookup = [
        "  ", " '", "' ", "''", " .", " :", "'.", "':",
        ". ", ".'", ": ", ":'", "..", ".:", ":.", "::",
    ]
    
    if len(ptr) < 3:
        print(f"line {textlinenum}: invalid block graphics escape", file=sys.stderr)
        sys.exit(1)
    
    block_str = ptr[1:3]
    for f, pattern in enumerate(lookup):
        if block_str == pattern:
            return 128 + f
    
    print(f"line {textlinenum}: invalid block graphics escape", file=sys.stderr)
    sys.exit(1)


def usage_help():
    """Print usage help"""
    print("pymakebas 1.3.3 - public domain by Russell Marks (python conversion).")
    print()
    print("usage: pymakebas [-hlpr] [-a line] [-i incr] [-n speccy_filename]")
    print("                [-o output_file] [-q line] [-s line] [input_file]")
    print()
    print("        -a      set auto-start line of basic file (default none).")
    print("        -h      give this usage help.")
    print("        -i      in labels mode, set line number increment.")
    print("        -l      use labels rather than line numbers.")
    print("        -n      set Spectrum filename (to be given in tape header).")
    print(f"        -o      specify output file (default `{DEFAULT_OUTPUT}').")
    print("        -p      output +3DOS file (default is .tap file).")
    print("        -q      convert tokens within quotes per line number (for VAL$).")
    print("                   If line number is 0, then tokenize within quotes globally.")
    print("        -r      output raw headerless file (default is .tap file).")
    print("        -s      in labels mode, set starting line number")


def parse_options(argv):
    """Parse command line options - matches C version exactly"""
    global output_format, use_labels, startline, autostart, autoincr
    global speccy_filename, startlabel, quot_tok_global, quot_tok_list
    global quot_tok_line_number_count, infile, outfile
    
    startlabel = ""
    infile = "-"
    outfile = DEFAULT_OUTPUT
    
    try:
        opts, args = getopt.getopt(argv, "a:hi:ln:o:pq:rs:")
    except getopt.GetoptError as e:
        optopt = e.opt if hasattr(e, 'opt') else '?'
        if e.msg == "option requires an argument":
            if optopt in ('a', 'q', 's'):
                print(f"The `{optopt}' option takes a line number arg.", file=sys.stderr)
            elif optopt == 'i':
                print("The `i' option takes a line incr. arg.", file=sys.stderr)
            elif optopt == 'n':
                print("The `n' option takes a Spectrum filename arg.", file=sys.stderr)
            elif optopt == 'o':
                print("The `o' option takes a filename arg.", file=sys.stderr)
            else:
                print(f"Option `{optopt}' not recognised.", file=sys.stderr)
        else:
            print(f"Option `{optopt}' not recognised.", file=sys.stderr)
        sys.exit(1)
    
    for opt, arg in opts:
        if opt == '-a':
            if arg.startswith('@'):
                if len(arg[1:]) > MAX_LABEL_LEN:
                    print("Auto-start label too long", file=sys.stderr)
                    sys.exit(1)
                startlabel = arg[1:]
            else:
                if not is_number(arg):
                    print("Auto-start line must be in the range 0 to 9999.", file=sys.stderr)
                    sys.exit(1)
                startline = int(arg)
                if startline > 9999:
                    print("Auto-start line must be in the range 0 to 9999.", file=sys.stderr)
                    sys.exit(1)
        elif opt == '-h':
            usage_help()
            sys.exit(0)
        elif opt == '-i':
            if not is_number(arg):
                print("Label line incr. must be in the range 1 to 1000.", file=sys.stderr)
                sys.exit(1)
            autoincr = int(arg)
            if autoincr < 1 or autoincr > 1000:
                print("Label line incr. must be in the range 1 to 1000.", file=sys.stderr)
                sys.exit(1)
        elif opt == '-l':
            use_labels = True
        elif opt == '-n':
            speccy_filename = arg[:10]
        elif opt == '-o':
            if len(arg) > 1023:
                print("Filename too long", file=sys.stderr)
                sys.exit(1)
            outfile = arg
        elif opt == '-p':
            output_format = OutputFormat.PLUS3DOS
        elif opt == '-q':
            if not is_number(arg) or len(arg) > MAX_LINE_NUMBER_LEN or int(arg) < 0 or int(arg) > 9999:
                print("Line number must be in the range 0 to 9999.\nSee usage for help\n\t\t% pymakebas -h", file=sys.stderr)
                sys.exit(1)
            if not quot_tok_global:
                quot_tok_global = (arg == '0')
            if not quot_tok_global:
                quot_tok_list.add_no_dupes(arg)
                quot_tok_line_number_count += 1
        elif opt == '-r':
            output_format = OutputFormat.RAW
        elif opt == '-s':
            if not is_number(arg):
                print("Label start line must be in the range 0 to 9999.", file=sys.stderr)
                sys.exit(1)
            autostart = int(arg)
            if autostart < 0 or autostart > 9999:
                print("Label start line must be in the range 0 to 9999.", file=sys.stderr)
                sys.exit(1)
    
    if len(args) > 1:
        usage_help()
        sys.exit(1)
    
    if len(args) == 1:
        if len(args[0]) > 1023:
            print("Filename too long", file=sys.stderr)
            sys.exit(1)
        infile = args[0]


def main():
    """Main program"""
    global output_format, use_labels, startline, autostart, autoincr
    global speccy_filename, startlabel, labels, label_lines, labelend
    global quot_tok_global, quot_tok_list, quot_tok_line_number_count
    global infile, outfile
    
    # Initialize globals
    output_format = OutputFormat.TAP
    use_labels = False
    startline = 0x8000
    autostart = 10
    autoincr = 2
    speccy_filename = ""
    startlabel = ""
    
    labels = []
    label_lines = []
    labelend = 0
    
    quot_tok_global = False
    quot_tok_list = QuoteTokList()
    quot_tok_line_number_count = 0
    
    infile = "-"
    outfile = DEFAULT_OUTPUT
    
    # Parse command line arguments
    parse_options(sys.argv[1:])
    
    # Open input file
    if infile == "-":
        in_file = sys.stdin
    else:
        try:
            in_file = open(infile, 'r')
        except IOError:
            print("Couldn't open input file.", file=sys.stderr)
            sys.exit(1)
    
    filebuf = bytearray()
    linenum = -1
    passnum = 1
    
    # Main processing loop
    while True:
        if use_labels:
            linenum = autostart - autoincr
        textlinenum = 0
        
        if passnum > 1:
            if infile == "-":
                print("Need seekable input for label support", file=sys.stderr)
                sys.exit(1)
            in_file.seek(0)
        
        while True:
            line = in_file.readline()
            if not line:
                break
            
            textlinenum += 1
            lastline = linenum
            
            # Remove newline
            if line.endswith('\n'):
                line = line[:-1]
            
            # Allow shell-style comments and ignore blank lines
            if not line or line[0] == '#':
                continue
            
            # Handle line continuation
            while line.endswith('\\'):
                cont_line = in_file.readline()
                if not cont_line:
                    line = line[:-1]  # remove backslash on EOF
                    break
                textlinenum += 1
                if cont_line.endswith('\n'):
                    cont_line = cont_line[:-1]
                line = line[:-1] + cont_line
            
            if len(line) >= BUF_SIZE - MAX_LABEL_LEN - 1:
                print(f"line {textlinenum}: line too big for input buffer", file=sys.stderr)
                sys.exit(1)
            
            # Get line number (or assign one)
            if use_labels:
                linestart_idx = 0
                linenum += autoincr
                if linenum > 9999:
                    msg = "try using `-s 1 -i 1'" if (autostart > 1 or autoincr > 1) else "too many lines!"
                    print(f"Generated line number is >9999 - {msg}", file=sys.stderr)
                    sys.exit(1)
            else:
                linestart_idx = 0
                while linestart_idx < len(line) and line[linestart_idx].isspace():
                    linestart_idx += 1
                if linestart_idx >= len(line) or not line[linestart_idx].isdigit():
                    print(f"line {textlinenum}: missing line number", file=sys.stderr)
                    sys.exit(1)
                
                # Parse line number - strtol sets linestart to point AFTER the number
                end_idx = linestart_idx
                while end_idx < len(line) and line[end_idx].isdigit():
                    end_idx += 1
                linenum = int(line[linestart_idx:end_idx])
                linestart_idx = end_idx  # Point to character after line number
                
                if linenum <= lastline:
                    print(f"line {textlinenum}: line no. not greater than previous one", file=sys.stderr)
                    sys.exit(1)
            
            if linenum < 0 or linenum > 9999:
                print(f"line {textlinenum}: line no. out of range", file=sys.stderr)
                sys.exit(1)
            
            # Skip remaining spaces after line number
            while linestart_idx < len(line) and line[linestart_idx].isspace():
                linestart_idx += 1
            
            # Check for line numbers in label mode
            if use_labels and linestart_idx < len(line) and line[linestart_idx].isdigit():
                print(f"line {textlinenum}: line number used in labels mode", file=sys.stderr)
                sys.exit(1)
            
            # Handle label definition
            if use_labels and linestart_idx < len(line) and line[linestart_idx] == '@':
                colon_idx = line.find(':', linestart_idx)
                if colon_idx == -1:
                    print(f"line {textlinenum}: incomplete token definition", file=sys.stderr)
                    sys.exit(1)
                if colon_idx - linestart_idx - 1 > MAX_LABEL_LEN:
                    print(f"line {textlinenum}: token too long", file=sys.stderr)
                    sys.exit(1)
                if passnum == 1:
                    label_name = line[linestart_idx + 1:colon_idx]
                    label_lines.append(linenum)
                    labels.append(label_name)
                    labelend += 1
                    if labelend >= MAX_LABELS:
                        print(f"line {textlinenum}: too many labels", file=sys.stderr)
                        sys.exit(1)
                    for f in range(labelend - 1):
                        if labels[f] == label_name:
                            print(f"line {textlinenum}: attempt to redefine label", file=sys.stderr)
                            sys.exit(1)
                    
                    linestart_idx = colon_idx + 1
                    while linestart_idx < len(line) and line[linestart_idx].isspace():
                        linestart_idx += 1
                    
                    # If now blank, don't insert an actual line
                    if linestart_idx >= len(line) or not line[linestart_idx]:
                        linenum -= autoincr
                        continue
                else:
                    linestart_idx = colon_idx + 1
                    while linestart_idx < len(line) and line[linestart_idx].isspace():
                        linestart_idx += 1
                    if linestart_idx >= len(line) or not line[linestart_idx]:
                        linenum -= autoincr
                        continue
            
            if use_labels and passnum == 1:
                continue
            
            # Extract line content and convert to bytearray
            linestart_str = line[linestart_idx:]
            linestart = bytearray(linestart_str.encode('latin-1'))
            
            # Make token comparison copy (lowercase, blanked-out strings)
            lcasebuf = bytearray()
            in_quotes = False
            for c in linestart:
                if c == ord('"'):
                    in_quotes = not in_quotes
                if in_quotes and c != ord('"') and not (quot_tok_global or (quot_tok_line_number_count and quot_tok_list.search(linenum))):
                    lcasebuf.append(32)  # space
                else:
                    lcasebuf.append(ord(chr(c).lower()))
            
            # Find REM statement
            remptr_idx = None
            rem_str = b"rem"
            pos = 0
            while True:
                pos = lcasebuf.find(rem_str, pos)
                if pos == -1:
                    break
                # Check boundaries
                prev_is_alpha = pos > 0 and chr(lcasebuf[pos - 1]).isalpha()
                next_is_alpha = pos + 3 < len(lcasebuf) and chr(lcasebuf[pos + 3]).isalpha()
                if not prev_is_alpha and not next_is_alpha:
                    remptr_idx = pos
                    # Mark REM token and following chars
                    linestart[pos] = REM_TOKEN_NUM
                    lcasebuf[pos] = REM_TOKEN_NUM
                    if pos + 1 < len(linestart):
                        linestart[pos + 1] = 1
                        lcasebuf[pos + 1] = 1
                    if pos + 2 < len(linestart):
                        linestart[pos + 2] = 1
                        lcasebuf[pos + 2] = 1
                    # Absorb trailing space
                    if pos + 3 < len(linestart) and linestart[pos + 3] == ord(' '):
                        linestart[pos + 3] = 1
                        lcasebuf[pos + 3] = 1
                    break
                pos += 1
            
            # Tokenize keywords
            # C code iterates through flat array: for (tarrptr = tokens; *tarrptr != NULL; tarrptr++)
            # toknum decrements when alttok is true, BEFORE checking if string is empty
            toknum = 256
            alttok = True
            
            # Flatten tokens array to match C structure (pairs become flat list)
            tokens_flat = []
            for token_pair in tokens:
                tokens_flat.append(token_pair[0])  # First token
                tokens_flat.append(token_pair[1] if len(token_pair) > 1 else "")  # Second token (may be empty)
            
            for token_str in tokens_flat:
                if alttok:
                    toknum -= 1
                alttok = not alttok
                
                # Handle VAL/VAL$ swap
                if toknum == VAL_TOKEN_NUM:
                    toknum = VALSTR_TOKEN_NUM
                elif toknum == VALSTR_TOKEN_NUM:
                    toknum = VAL_TOKEN_NUM
                
                # Skip empty strings (but toknum already decremented if alttok was true)
                if not token_str:
                    continue
                
                toklen = len(token_str)
                token_bytes = token_str.lower().encode('latin-1')
                
                # Find all occurrences
                # C code: strstr stops at null terminator, so REM prevents tokenization after it
                pos = 0
                while True:
                    # Check if we've reached REM (null terminator)
                    if remptr_idx is not None and pos >= remptr_idx:
                        break
                    pos = lcasebuf.find(token_bytes, pos)
                    if pos == -1:
                        break
                    # Stop if we've reached REM
                    if remptr_idx is not None and pos >= remptr_idx:
                        break
                    
                    # Check it's not in the middle of a word (except for <>, <=, >=)
                    # C code: (*tarrptr)[0] == '<' || (*tarrptr)[1] == '=' || (!isalpha(ptr[-1]) && !isalpha(ptr[toklen]))
                    # In C, isalpha() returns 0 for values >= 128, so we need to check < 128 first
                    prev_is_alpha = False
                    if pos > 0 and lcasebuf[pos - 1] < 128:
                        prev_is_alpha = chr(lcasebuf[pos - 1]).isalpha()
                    next_is_alpha = False
                    if pos + toklen < len(lcasebuf) and lcasebuf[pos + toklen] < 128:
                        next_is_alpha = chr(lcasebuf[pos + toklen]).isalpha()
                    
                    if token_str[0] == '<' or (len(token_str) > 1 and token_str[1] == '=') or (not prev_is_alpha and not next_is_alpha):
                        # Replace token
                        linestart[pos] = toknum
                        lcasebuf[pos] = toknum
                        for f in range(1, toklen):
                            if pos + f < len(linestart):
                                linestart[pos + f] = 1
                                lcasebuf[pos + f] = 1
                        
                        # Absorb trailing spaces
                        f = toklen
                        while pos + f < len(linestart) and linestart[pos + f] == ord(' '):
                            linestart[pos + f] = 1
                            lcasebuf[pos + f] = 1
                            f += 1
                        
                        # Special handling for BIN token
                        if toknum == BIN_TOKEN_NUM:
                            linestart[pos] = 1
                            lcasebuf[pos] = 1
                            if pos + f - 1 < len(linestart):
                                linestart[pos + f - 1] = toknum
                                lcasebuf[pos + f - 1] = toknum
                    
                    pos += toklen
            
            # Replace labels with line numbers
            if use_labels:
                ptr = 0
                while True:
                    ptr = linestart.find(ord('@'), ptr)
                    if ptr == -1:
                        break
                    
                    # Check for escape
                    if ptr > 0 and linestart[ptr - 1] == ord('\\'):
                        ptr += 1
                        continue
                    
                    # Try to match label
                    ptr += 1
                    matched = False
                    for f in range(labelend):
                        label = labels[f]
                        len_label = len(label)
                        label_bytes = label.encode('latin-1')
                        if linestart[ptr:ptr + len_label] == label_bytes:
                            next_char = linestart[ptr + len_label] if ptr + len_label < len(linestart) else 0
                            if next_char < 33 or next_char > 126 or next_char == ord(':'):
                                # Replace label with line number
                                numbuf = str(label_lines[f]).encode('latin-1')
                                # Remove label text
                                new_linestart = linestart[:ptr - 1] + numbuf + linestart[ptr + len_label:]
                                linestart = new_linestart
                                ptr += len(numbuf)
                                matched = True
                                break
                    
                    if not matched:
                        print(f"line {textlinenum}: undefined label", file=sys.stderr)
                        sys.exit(1)
            
            # Restore REM token if needed
            if remptr_idx is not None:
                linestart[remptr_idx] = REM_TOKEN_NUM
            
            # Process line and build output
            outbuf = bytearray()
            ptr = 0
            in_rem = False
            in_deffn = False
            in_quotes = False
            
            while ptr < len(linestart):
                if len(outbuf) > OUTBUF_SIZE - 10:
                    print(f"line {textlinenum}: line too big", file=sys.stderr)
                    sys.exit(1)
                
                c = linestart[ptr]
                
                if c == ord('"'):
                    in_quotes = not in_quotes
                
                # Skip 0x01 chars, tabs, and spaces (when not in quotes/rem)
                if c == 1 or c == 9 or (not in_quotes and not in_rem and c == ord(' ')):
                    ptr += 1
                    continue
                
                if c == DEFFN_TOKEN_NUM:
                    in_deffn = True
                
                if c == REM_TOKEN_NUM:
                    in_rem = True
                
                # Handle escape sequences
                if c == ord('\\') and ptr + 1 < len(linestart):
                    esc_char = chr(linestart[ptr + 1])
                    if esc_char.isalpha() and esc_char.lower() not in "vwxyz":
                        outbuf.append(144 + ord(esc_char.lower()) - ord('a'))
                    else:
                        if esc_char == '\\':
                            outbuf.append(ord('\\'))
                        elif esc_char == '@':
                            outbuf.append(ord('@'))
                        elif esc_char == '*':
                            outbuf.append(127)  # copyright symbol
                        elif esc_char in ("'", '.', ':', ' '):
                            # Block graphics
                            if ptr + 3 <= len(linestart):
                                block_str = ''.join(chr(b) for b in linestart[ptr:ptr + 3])
                                block_val = grok_block(block_str, textlinenum)
                                outbuf.append(block_val)
                                ptr += 1
                            else:
                                print(f"line {textlinenum}: invalid block graphics escape", file=sys.stderr)
                                sys.exit(1)
                        elif esc_char == '{':
                            # Direct character code
                            end_brace = linestart.find(ord('}'), ptr + 2)
                            if end_brace == -1:
                                print(f"line {textlinenum}: unclosed brace in eight-bit character code", file=sys.stderr)
                                sys.exit(1)
                            code_str = linestart[ptr + 2:end_brace].decode('latin-1', errors='ignore')
                            try:
                                num_ascii = int(code_str, 0)  # Supports decimal, octal, hex
                            except ValueError:
                                print(f"line {textlinenum}: invalid character code", file=sys.stderr)
                                sys.exit(1)
                            if num_ascii < 0 or num_ascii > 255:
                                print(f"line {textlinenum}: eight-bit character code out of range", file=sys.stderr)
                                sys.exit(1)
                            outbuf.append(num_ascii)
                            ptr = end_brace - 1
                        else:
                            print(f"line {textlinenum}: warning: unknown escape `{esc_char}', inserting literally", file=sys.stderr)
                            outbuf.append(linestart[ptr + 1])
                    ptr += 2
                    continue
                
                # Handle numbers
                if not in_rem and not in_quotes:
                    prev_char = linestart[ptr - 1] if ptr > 0 else ord(' ')
                    prev_is_alpha = chr(prev_char).isalpha() if prev_char < 128 else False
                    
                    # Check if this looks like the start of a number
                    is_num_start = False
                    if chr(c).isdigit():
                        is_num_start = True
                    elif ptr + 1 < len(linestart):
                        next_char = linestart[ptr + 1]
                        if c == ord('.') and chr(next_char).isdigit():
                            is_num_start = True
                        elif c in (ord('-'), ord('+')) and (chr(next_char).isdigit() or 
                                                              (chr(next_char) == '.' and ptr + 2 < len(linestart) and chr(linestart[ptr + 2]).isdigit())):
                            is_num_start = True
                    
                    if is_num_start and not prev_is_alpha and prev_char != BIN_TOKEN_NUM:
                        # Parse number using strtod equivalent
                        # Convert bytearray slice to string for parsing
                        remaining_str = linestart[ptr:].decode('latin-1', errors='ignore')
                        try:
                            # Use a regex or manual parsing to find where the number ends
                            # strtod() stops at the first character that cannot be part of a number
                            import re
                            # Match a number: optional sign, digits, optional decimal point and more digits, optional exponent
                            match = re.match(r'[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?', remaining_str)
                            if match:
                                num_str = match.group(0)
                                num = float(num_str)
                                num_end = len(num_str)
                                ptr2 = ptr + num_end
                                
                                # Output number text (original bytes)
                                outbuf.extend(linestart[ptr:ptr2])
                                
                                # Output inline FP representation
                                outbuf.append(0x0e)
                                success, num_exp, num_mantissa = dbl2spec(num)
                                if not success:
                                    print(f"line {textlinenum}: exponent out of range (number too big)", file=sys.stderr)
                                    sys.exit(1)
                                outbuf.append(num_exp)
                                outbuf.append((num_mantissa >> 24) & 0xFF)
                                outbuf.append((num_mantissa >> 16) & 0xFF)
                                outbuf.append((num_mantissa >> 8) & 0xFF)
                                outbuf.append(num_mantissa & 0xFF)
                                ptr = ptr2
                                continue
                        except (ValueError, IndexError, AttributeError):
                            # Not a valid number, fall through to normal character handling
                            pass
                    elif prev_char == BIN_TOKEN_NUM:
                        # Number after BIN token
                        num_str_bytes = linestart[ptr:].decode('latin-1', errors='ignore')
                        num_val, ptr2_str = grok_binary(num_str_bytes, textlinenum)
                        num = float(num_val)
                        ptr2 = ptr + (len(num_str_bytes) - len(ptr2_str))
                        
                        # Output number text
                        outbuf.extend(linestart[ptr:ptr2])
                        
                        # Output inline FP representation
                        outbuf.append(0x0e)
                        success, num_exp, num_mantissa = dbl2spec(num)
                        if not success:
                            print(f"line {textlinenum}: exponent out of range (number too big)", file=sys.stderr)
                            sys.exit(1)
                        outbuf.append(num_exp)
                        outbuf.append((num_mantissa >> 24) & 0xFF)
                        outbuf.append((num_mantissa >> 16) & 0xFF)
                        outbuf.append((num_mantissa >> 8) & 0xFF)
                        outbuf.append(num_mantissa & 0xFF)
                        ptr = ptr2
                        continue
                
                # Special DEF FN case
                if in_deffn:
                    if c == ord('='):
                        in_deffn = False
                    else:
                        if c in (ord(','), ord(')')):
                            outbuf.append(0x0e)
                            outbuf.extend([0, 0, 0, 0, 0])
                            outbuf.append(c)
                            ptr += 1
                            continue
                        
                        if c != ord(' '):
                            if c == ord('='):
                                in_deffn = False
                            outbuf.append(c)
                            ptr += 1
                            continue
                else:
                    # Normal character output
                    outbuf.append(c)
                    ptr += 1
            
            # Add terminating CR
            outbuf.append(0x0d)
            
            # Check buffer size
            linelen = len(outbuf)
            if len(filebuf) + 4 + linelen > FILEBUF_SIZE:
                print("program too big!", file=sys.stderr)
                sys.exit(1)
            
            # Write line to filebuf
            filebuf.extend(struct.pack('>H', linenum))  # line number (big-endian)
            filebuf.extend(struct.pack('<H', linelen))  # line length (little-endian)
            filebuf.extend(outbuf)
        
        passnum += 1
        if not (use_labels and passnum <= 2):
            break
    
    if in_file != sys.stdin:
        in_file.close()
    
    # Check auto-start label
    if startlabel:
        if not use_labels:
            print("Auto-start label specified, but not using labels!", file=sys.stderr)
            sys.exit(1)
        found = False
        for f in range(labelend):
            if labels[f] == startlabel:
                startline = label_lines[f]
                found = True
                break
        if not found:
            print("Auto-start label is undefined", file=sys.stderr)
            sys.exit(1)
    
    # Write output file
    if outfile == "-":
        out_file = sys.stdout.buffer
    else:
        try:
            out_file = open(outfile, 'wb')
        except IOError:
            print("Couldn't open output file.", file=sys.stderr)
            sys.exit(1)
    
    siz = len(filebuf)
    
    if output_format == OutputFormat.PLUS3DOS:
        # Make header
        headerbuf = bytearray(128)
        headerbuf[0:10] = b"PLUS3DOS\032\001"
        total_size = siz + 128
        headerbuf[11] = total_size & 0xFF
        headerbuf[12] = (total_size >> 8) & 0xFF
        headerbuf[13] = (total_size >> 16) & 0xFF
        headerbuf[14] = (total_size >> 24) & 0xFF
        headerbuf[15] = 0  # BASIC
        headerbuf[16] = siz & 0xFF
        headerbuf[17] = (siz >> 8) & 0xFF
        headerbuf[18] = startline & 0xFF
        headerbuf[19] = (startline >> 8) & 0xFF
        headerbuf[20] = siz & 0xFF
        headerbuf[21] = (siz >> 8) & 0xFF
        
        chk = sum(headerbuf[:127]) & 0xFF
        out_file.write(headerbuf[:127])
        out_file.write(bytes([chk]))
    
    elif output_format == OutputFormat.TAP:
        # Make header
        headerbuf = bytearray(17)
        headerbuf[0] = 0
        filename_bytes = speccy_filename.encode('latin-1')[:10]
        headerbuf[1:1+len(filename_bytes)] = filename_bytes
        # Pad with spaces
        for f in range(len(filename_bytes), 10):
            headerbuf[1 + f] = 32
        headerbuf[11] = siz & 0xFF
        headerbuf[12] = (siz >> 8) & 0xFF
        headerbuf[13] = startline & 0xFF
        headerbuf[14] = (startline >> 8) & 0xFF
        headerbuf[15] = siz & 0xFF
        headerbuf[16] = (siz >> 8) & 0xFF
        
        # Write header
        chk = 0
        out_file.write(bytes([19, 0, chk]))
        for f in range(17):
            chk ^= headerbuf[f]
        out_file.write(headerbuf)
        out_file.write(bytes([chk]))
        
        # Write tap bit for data block
        # C code: fprintf(out, "%c%c%c", (siz + 2) & 255, (siz + 2) >> 8, chk = 255);
        # This writes: low_byte, high_byte, 255 (initial checksum)
        # Then calculates: for (f = 0; f < siz; f++) chk ^= filebuf[f];
        chk = 255
        out_file.write(struct.pack('<H', siz + 2))
        out_file.write(bytes([chk]))  # Write initial checksum (255)
        # Now calculate checksum by XORing with filebuf
        for f in range(siz):
            chk ^= filebuf[f]
    
    # Write file data
    out_file.write(filebuf)
    
    if output_format == OutputFormat.TAP:
        out_file.write(bytes([chk]))
    
    if out_file != sys.stdout.buffer:
        out_file.close()
    
    quot_tok_list.free()
    sys.exit(0)


if __name__ == '__main__':
    main()
