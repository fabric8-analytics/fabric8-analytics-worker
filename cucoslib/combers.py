from re import compile as re_compile

def comb_binwalk(output):
    "Comb binwalk output"
    if not output:
        return None

    matcher = re_compile('^\d{,8}\s*0x[A-Fa-f0-9]{,8}\s*(.*)$')
    matched = []
    for line in output:
        match = matcher.match(line)
        if match:
            matched.append(match.groups(1)[0])
 
    return matched

def comb_linguist(output):
    "Comb linguist output"
    if not output:
        return None

    def _get_value(line):
        "Get Value from 'Key: Value'"
        return line.split(':', 1)[1].strip()

    lines, sloc = 0, 0
    lines_matcher = re_compile('(\d+) lines \((\d+) sloc\)')
    m = lines_matcher.search(output[0])

    if m:
        lines, sloc = m.groups(1)[0], m.groups(2)[0]

    output = {'type': _get_value(output[1]),
              'mime': _get_value(output[2]),
              'language': _get_value(output[3]),
              'lines': lines,
              'sloc' : sloc}

    return output
