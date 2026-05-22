#!/usr/bin/env python3
import ast
import json
import os
import re
import time
import traceback
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from groq import Groq
except ImportError:
    raise SystemExit(
        'Missing dependency: install with `pip install -r requirements.txt`'
    )

if load_dotenv is not None:
    load_dotenv()

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
if not GROQ_API_KEY:
    raise SystemExit(
        'Please set GROQ_API_KEY in your environment or .env file.\n'
        'Copy the key from your notebook into .env or export it first.'
    )

SYSTEM_PROMPT = '''You are an expert Python programmer.

Complete the requested function.

RULES:
- Return ONLY valid Python code
- No markdown
- No explanations
- No comments outside the code
- Preserve function signature
- Complete implementation only'''

MODELS = {
    'openai': 'openai/gpt-oss-120b',
    'meta': 'llama-3.1-8b-instant',
    'alibaba': 'qwen/qwen3-32b'
}

VARIATIONS = [
    'baseline','concise','verbose','expert','academic',
    'casual','production','no_examples','plain_text','negative_instruction'
]

PROBLEMS = [
    {
        'id': 'humaneval_000',
        'entry': 'has_close_elements',
        'ref': 'def has_close_elements(numbers, threshold):\n    for i in range(len(numbers)):\n        for j in range(i+1,len(numbers)):\n            if abs(numbers[i]-numbers[j])<threshold: return True\n    return False',
        'test': '\ndef check(c):\n    assert c([1.0,2.0,3.9,4.0,5.0,2.2],0.3)==True\n    assert c([1.0,2.0,3.9,4.0,5.0,2.2],0.05)==False\n    assert c([1.0,2.0,5.9,4.0,5.0],0.95)==True\n    assert c([1.0,2.0,3.0,4.0,5.0,2.0],0.1)==True',
        'prompts': {
            'baseline': 'Complete this Python function:\n\nfrom typing import List\n\ndef has_close_elements(numbers: List[float], threshold: float) -> bool:\n    """Check if any two numbers are closer than threshold.\n    >>> has_close_elements([1.0,2.0,3.0],0.5)\n    False\n    >>> has_close_elements([1.0,2.8,3.0,4.0,5.0,2.0],0.3)\n    True\n    """',
            'concise': 'Complete: def has_close_elements(numbers, threshold): """Return True if any two numbers differ by less than threshold."""',
            'verbose': 'Implement has_close_elements. Check every pair of distinct elements. If absolute difference < threshold, return True; otherwise False.\n\ndef has_close_elements(numbers: list, threshold: float) -> bool:',
            'expert': 'Implement O(n^2) pairwise proximity check. Return True iff exists i!=j with |a[i]-a[j]|<threshold.\n\ndef has_close_elements(numbers, threshold):',
            'academic': 'Given sequence S and epsilon>0, determine if distinct i,j exist s.t. |S[i]-S[j]|<epsilon.\n\ndef has_close_elements(numbers: list, threshold: float) -> bool:',
            'casual': 'Write a function that checks if any two numbers in a list are really close together (less than threshold apart).\n\ndef has_close_elements(numbers, threshold):',
            'production': 'def has_close_elements(numbers: list, threshold: float) -> bool:\n    """Args:\n        numbers: list of floats\n        threshold: proximity threshold\n    Returns:\n        bool: True if any pair within threshold\n    """',
            'no_examples': 'Complete: def has_close_elements(numbers, threshold):\n    """Check if any two numbers are closer than threshold."""',
            'plain_text': 'Write a Python function named has_close_elements that takes a list of floats and a threshold. Return True if any two elements differ by less than the threshold.',
            'negative_instruction': 'Complete this. Do NOT use sorting. Do NOT import numpy.\n\ndef has_close_elements(numbers: list, threshold: float) -> bool:\n    """Check if any two numbers differ by less than threshold."""'
        }
    },
    {
        'id': 'humaneval_001',
        'entry': 'separate_paren_groups',
        'ref': 'def separate_paren_groups(paren_string):\n    result=[]; buf=[]; depth=0\n    for c in paren_string:\n        if c==" ": continue\n        buf.append(c)\n        if c=="(": depth+=1\n        elif c==")": depth-=1\n        if depth==0 and buf: result.append("".join(buf)); buf=[]\n    return result',
        'test': '\ndef check(c):\n    assert c("(()()) ((())) () ((())()())")==["(()())","((()))","()","((())()())"]\n    assert c("() (()) ((())) (((())))")==["()","(())","((()))","(((())))"]\n    assert c("( ) (( )) (( )( ))")==["()","(())","(()())"]',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List\ndef separate_paren_groups(paren_string: str) -> List[str]:\n    """Split balanced top-level paren groups into a list. Ignore spaces.\n    >>> separate_paren_groups("( ) (( ))")\n    ["()", "(())"]\n    """',
            'concise': 'Complete: def separate_paren_groups(s): """Return list of balanced top-level paren groups."""',
            'verbose': 'Implement separate_paren_groups. Parse a string of balanced parenthesis groups separated by spaces. Return each top-level group as an element in a list.',
            'expert': 'Tokenize string into maximal balanced paren substrings using depth tracking. Ignore whitespace.\n\ndef separate_paren_groups(paren_string):',
            'academic': 'Given string over {(,),space}, partition into maximal substrings forming balanced expressions.\n\ndef separate_paren_groups(paren_string: str):',
            'casual': 'Write a function that takes "() (()) ((()))" and breaks it into separate paren groups as a list.',
            'production': 'def separate_paren_groups(paren_string: str) -> list:\n    """Parse balanced parenthesis groups.\n    Args: paren_string: space-separated balanced groups\n    Returns: list of group strings\n    """',
            'no_examples': 'Complete: def separate_paren_groups(paren_string): """Split string of balanced paren groups into a list."""',
            'plain_text': 'Write a Python function separate_paren_groups(paren_string) that returns balanced top-level paren groups as a list.',
            'negative_instruction': 'Complete this. Do NOT use regex. Do NOT use split().\n\ndef separate_paren_groups(paren_string):'
        }
    },
    {
        'id': 'humaneval_002',
        'entry': 'truncate_number',
        'ref': 'def truncate_number(number):\n    return number % 1.0',
        'test': '\ndef check(c):\n    assert c(3.5)==0.5\n    assert abs(c(1.33)-0.33)<1e-6\n    assert abs(c(123.456)-0.456)<1e-6',
        'prompts': {
            'baseline': 'Complete: def truncate_number(number: float) -> float:\n    """Return the decimal part of a positive float.\n    >>> truncate_number(3.5)\n    0.5\n    """',
            'concise': 'Complete: def truncate_number(x: float) -> float: """Return fractional part of positive float."""',
            'verbose': 'Implement truncate_number. Given a positive float like 3.5, return only the decimal portion (0.5).',
            'expert': 'Return x - floor(x) for positive float x.\n\ndef truncate_number(number: float) -> float:',
            'academic': 'For x in R+, compute the fractional part: x - floor(x).\n\ndef truncate_number(number: float) -> float:',
            'casual': 'Just return the decimal part of a float. Like 3.5 gives 0.5, 2.7 gives 0.7.',
            'production': 'def truncate_number(number: float) -> float:\n    """Extract decimal portion of positive float.\n    Args: number: positive float\n    Returns: fractional part\n    """',
            'no_examples': 'Complete: def truncate_number(number): """Return the decimal part of a positive float."""',
            'plain_text': 'Write truncate_number(number) that returns only the decimal part of a float.',
            'negative_instruction': 'Complete this. Do NOT use math.floor. Do NOT use int() casting.\n\ndef truncate_number(number: float) -> float:'
        }
    },
    {
        'id': 'humaneval_003',
        'entry': 'below_zero',
        'ref': 'def below_zero(operations):\n    bal=0\n    for op in operations:\n        bal+=op\n        if bal<0: return True\n    return False',
        'test': '\ndef check(c):\n    assert c([])==False\n    assert c([1,2,-3,1,2,-3])==False\n    assert c([1,2,-4,5,6])==True\n    assert c([1,-1,2,-2,5,-5,4,-5])==True',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List\ndef below_zero(operations: List[int]) -> bool:\n    """Detect if bank balance goes below zero.\n    >>> below_zero([1,2,3])\n    False\n    >>> below_zero([1,2,-4,5])\n    True\n    """',
            'concise': 'Complete: def below_zero(ops): """Return True if running sum ever < 0."""',
            'verbose': 'Implement below_zero. Simulate a bank account starting at 0. Apply each integer operation. Return True the moment balance goes negative.',
            'expert': 'Detect if prefix sum of integer list ever becomes strictly negative.\n\ndef below_zero(operations):',
            'academic': 'Given sequence a_1..a_n, determine if any partial sum < 0.\n\ndef below_zero(operations: list) -> bool:',
            'casual': 'Check if a bank balance ever drops below zero. Start at 0, add each number, return True if it hits negative.',
            'production': 'def below_zero(operations: list) -> bool:\n    """Detect negative balance during transaction processing.\n    Args: operations: list of int amounts\n    Returns: True if balance drops below zero\n    """',
            'no_examples': 'Complete: def below_zero(operations): """Return True if running total ever drops below zero."""',
            'plain_text': 'Write below_zero(operations) that returns True if the running sum ever goes negative.',
            'negative_instruction': 'Complete this. Do NOT use any() with generators. Do NOT use sum().\n\ndef below_zero(operations: list) -> bool:'
        }
    },
    {
        'id': 'humaneval_004',
        'entry': 'mean_absolute_deviation',
        'ref': 'def mean_absolute_deviation(numbers):\n    mean=sum(numbers)/len(numbers)\n    return sum(abs(x-mean) for x in numbers)/len(numbers)',
        'test': '\ndef check(c):\n    assert abs(c([1.0,2.0,3.0])-2.0/3.0)<1e-6\n    assert abs(c([1.0,2.0,3.0,4.0])-1.0)<1e-6\n    assert abs(c([1.0,2.0,3.0,4.0,5.0])-6.0/5.0)<1e-6',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List\ndef mean_absolute_deviation(numbers: List[float]) -> float:\n    """Calculate MAD: average absolute difference from mean.\n    >>> mean_absolute_deviation([1.0,2.0,3.0,4.0])\n    1.0\n    """',
            'concise': 'Complete: def mean_absolute_deviation(numbers): """Compute MAD: mean of absolute deviations from the mean."""',
            'verbose': 'Implement mean_absolute_deviation. Compute the mean, then find the average of absolute differences between each element and that mean.',
            'expert': 'Return (1/n)*sum(|x_i - mean(x)|) for a float list.\n\ndef mean_absolute_deviation(numbers):',
            'academic': 'Compute MAD(X)=E[|X-E[X]|] for empirical distribution.\n\ndef mean_absolute_deviation(numbers: list) -> float:',
            'casual': 'Find the average distance each number is from the mean of the list.',
            'production': 'def mean_absolute_deviation(numbers: list) -> float:\n    """Calculate MAD for statistical analysis.\n    Args: numbers: list of floats\n    Returns: mean absolute deviation\n    """',
            'no_examples': 'Complete: def mean_absolute_deviation(numbers): """Calculate mean absolute deviation."""',
            'plain_text': 'Write mean_absolute_deviation(numbers) that computes the mean absolute deviation.',
            'negative_instruction': 'Complete this. Do NOT import numpy or statistics.\n\ndef mean_absolute_deviation(numbers: list) -> float:'
        }
    },
    {
        'id': 'humaneval_005',
        'entry': 'intersperse',
        'ref': 'def intersperse(numbers, delimeter):\n    if not numbers: return []\n    result=[]\n    for i,n in enumerate(numbers):\n        result.append(n)\n        if i<len(numbers)-1: result.append(delimeter)\n    return result',
        'test': '\ndef check(c):\n    assert c([],4)==[]\n    assert c([1,2,3],4)==[1,4,2,4,3]\n    assert c([1,2,3,4,5],8)==[1,8,2,8,3,8,4,8,5]',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List\ndef intersperse(numbers: List[int], delimeter: int) -> List[int]:\n    """Insert delimeter between every pair of consecutive elements.\n    >>> intersperse([1,2,3],4)\n    [1,4,2,4,3]\n    """',
            'concise': 'Complete: def intersperse(numbers, delimeter): """Insert delimeter between all list elements."""',
            'verbose': 'Implement intersperse. Given a list and a delimiter, return a new list with the delimiter between every adjacent pair.',
            'expert': 'Interleave delimiter between consecutive elements.\n\ndef intersperse(numbers, delimeter):',
            'academic': 'Construct b s.t. b[2i]=a[i] and b[2i+1]=d for i<n-1.\n\ndef intersperse(numbers):',
            'casual': 'Put a number between every element of a list. Like [1,2,3] with 4 becomes [1,4,2,4,3].',
            'production': 'def intersperse(numbers: list, delimeter: int) -> list:\n    """Insert delimiter between every consecutive pair.\n    Args: numbers: input list; delimeter: value to insert\n    """',
            'no_examples': 'Complete: def intersperse(numbers, delimeter): """Insert the delimeter between each pair of elements."""',
            'plain_text': 'Write intersperse(numbers, delimeter) that inserts delimeter between every adjacent pair of elements.',
            'negative_instruction': 'Complete this. Do NOT use list comprehensions. Do NOT use zip().\n\ndef intersperse(numbers: list, delimeter: int) -> list:'
        }
    },
    {
        'id': 'humaneval_006',
        'entry': 'parse_nested_parens',
        'ref': 'def parse_nested_parens(paren_string):\n    def depth(s):\n        d=mx=0\n        for c in s:\n            if c=="(": d+=1; mx=max(mx,d)\n            elif c==")": d-=1\n        return mx\n    return [depth(g) for g in paren_string.split() if g]',
        'test': '\ndef check(c):\n    assert c("(()()) ((())) () ((())()())")==[2,3,1,3]\n    assert c("() (()) ((())) (((())))")==[1,2,3,4]',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List\ndef parse_nested_parens(paren_string: str) -> List[int]:\n    """Return max nesting depth of each space-separated paren group.\n    >>> parse_nested_parens("(()()) ((()))")\n    [2,3]\n    """',
            'concise': 'Complete: def parse_nested_parens(s): """Return max nesting depth of each paren group."""',
            'verbose': 'Implement parse_nested_parens. Split input by spaces, then for each group compute the maximum nesting depth.',
            'expert': 'For each top-level paren group, compute max stack depth.\n\ndef parse_nested_parens(paren_string):',
            'academic': 'Given string of paren groups, return sequence of max depths.\n\ndef parse_nested_parens(paren_string: str) -> list:',
            'casual': 'Split the string into paren groups and figure out the max nesting depth of each one.',
            'production': 'def parse_nested_parens(paren_string: str) -> list:\n    """Parse nesting depths of parenthesis groups.\n    Args: paren_string: space-separated paren groups\n    Returns: list of max nesting depths\n    """',
            'no_examples': 'Complete: def parse_nested_parens(paren_string): """Return max nesting depth of each paren group."""',
            'plain_text': 'Write parse_nested_parens(paren_string) returning max nesting depths for each space-separated paren group.',
            'negative_instruction': 'Complete this. Do NOT use a stack or collections.\n\ndef parse_nested_parens(paren_string: str) -> list:'
        }
    },
    {
        'id': 'humaneval_007',
        'entry': 'filter_by_substring',
        'ref': 'def filter_by_substring(strings, substring):\n    return [s for s in strings if substring in s]',
        'test': '\ndef check(c):\n    assert c([],\'a\')==[]\n    assert c([\'abc\',\'bacd\',\'cde\',\'array\'],\'a\')==[\'abc\',\'bacd\',\'array\']\n    assert c([\'abc\',\'def\',\'ghi\'],\'x\')==[]',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List\ndef filter_by_substring(strings: List[str], substring: str) -> List[str]:\n    """Keep only strings containing the substring.\n    >>> filter_by_substring([\'abc\',\'bcd\'],\'bc\')\n    [\'abc\', \'bcd\']\n    """',
            'concise': 'Complete: def filter_by_substring(strings, substring): """Keep only strings containing substring."""',
            'verbose': 'Implement filter_by_substring. Given a list of strings, return only those containing the given substring.',
            'expert': 'Return sublist where each element contains the given substring.\n\ndef filter_by_substring(strings, substring):',
            'academic': 'Filter S to retain s_i such that substring is contained in s_i.\n\ndef filter_by_substring(strings: list, substring: str) -> list:',
            'casual': 'Filter a list to keep only strings that have a certain substring in them.',
            'production': 'def filter_by_substring(strings: list, substring: str) -> list:\n    """Filter to strings containing substring.\n    Args: strings: list; substring: search term\n    """',
            'no_examples': 'Complete this. Do NOT use filter(). Do NOT use regex.\n\ndef filter_by_substring(strings: list, substring: str) -> list:',
            'plain_text': 'Write filter_by_substring(strings, substring) that returns only strings from the list that contain substring.',
            'negative_instruction': 'Complete this. Do NOT use filter(). Do NOT use regex.\n\ndef filter_by_substring(strings: list, substring: str) -> list:'
        }
    },
    {
        'id': 'humaneval_008',
        'entry': 'sum_product',
        'ref': 'def sum_product(numbers):\n    s=sum(numbers) if numbers else 0\n    p=1\n    for n in numbers: p*=n\n    return (s,p)',
        'test': '\ndef check(c):\n    assert c([])==(0,1)\n    assert c([1,1,1])==(3,1)\n    assert c([100,0])==(100,0)\n    assert c([3,5,7])==(15,105)',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List,Tuple\ndef sum_product(numbers: List[int]) -> Tuple[int,int]:\n    """Return (sum, product) of list.\n    >>> sum_product([1,2,3,4])\n    (10,24)\n    """',
            'concise': 'Complete: def sum_product(numbers): """Return (sum, product) of list elements."""',
            'verbose': 'Implement sum_product. Return a tuple: first element is sum, second is product. Empty list returns (0,1).',
            'expert': 'Return (sum(a), prod(a)), empty->[0,1].\n\ndef sum_product(numbers):',
            'academic': 'Compute (S,P) where S=sum(a_i), P=prod(a_i). Empty->(0,1).\n\ndef sum_product(numbers):',
            'casual': 'Return the sum and product of a list as a tuple. Empty list should give (0,1).',
            'production': 'def sum_product(numbers: list) -> tuple:\n    """Compute aggregate statistics.\n    Args: numbers: list of ints\n    Returns: (sum, product) tuple\n    """',
            'no_examples': 'Complete: def sum_product(numbers): """Return (sum, product). Empty list returns (0,1)."""',
            'plain_text': 'Write sum_product(numbers) returning a tuple of the sum and product of all numbers.',
            'negative_instruction': 'Complete this. Do NOT use functools.reduce(). Do NOT use math.prod().\n\ndef sum_product(numbers: list) -> tuple:'
        }
    },
    {
        'id': 'humaneval_009',
        'entry': 'rolling_max',
        'ref': 'def rolling_max(numbers):\n    result=[]; mx=float("-inf")\n    for n in numbers:\n        mx=max(mx,n); result.append(mx)\n    return result',
        'test': '\ndef check(c):\n    assert c([])==[]\n    assert c([1,2,3,2,3,4,2])==[1,2,3,3,3,4,4]\n    assert c([3,2,1])==[3,3,3]',
        'prompts': {
            'baseline': 'Complete:\nfrom typing import List\ndef rolling_max(numbers: List[int]) -> List[int]:\n    """Return running maximum of a list.\n    >>> rolling_max([1,2,3,2,3,4,2])\n    [1,2,3,3,3,4,4]\n    """',
            'concise': 'Complete: def rolling_max(numbers): """Return cumulative maximum at each position."""',
            'verbose': 'Implement rolling_max. For each index i, the output is the maximum value seen so far (indices 0 to i inclusive).',
            'expert': 'Compute prefix-max sequence of integer list.\n\ndef rolling_max(numbers):',
            'academic': 'Construct b where b[i]=max(a[0..i]).\n\ndef rolling_max(numbers: list) -> list:',
            'casual': 'For each position in the list, track the max seen so far. Return those max values as a list.',
            'production': 'def rolling_max(numbers: list) -> list:\n    """Compute running maximum sequence.\n    Args: numbers: list of ints\n    Returns: list of running maxima\n    """',
            'no_examples': 'Complete: def rolling_max(numbers): """Return list of running maximums up to each index."""',
            'plain_text': 'Write rolling_max(numbers) returning a list where each element is the max of all elements up to that position.',
            'negative_instruction': 'Complete this. Do NOT use itertools.accumulate(). Do NOT use numpy.\n\ndef rolling_max(numbers: list) -> list:'
        }
    }
]

OUTPUT_PATH = Path('results.json')


def extract_python_code(text):
    if text is None:
        return None
    text = re.sub(r'```python', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```', '', text)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = text.strip()
    match = re.search(r'(from\s+\w+\s+import|import\s+\w+|def\s+\w+\s*\()', text)
    if match:
        text = text[match.start():]
    return text.strip()


def instruction_compliance(raw_text):
    if raw_text is None:
        return False
    forbidden_patterns = [r'<think>', r'```', r'Here is', r'Explanation']
    return not any(re.search(p, raw_text, flags=re.IGNORECASE) for p in forbidden_patterns)


def syntax_valid(code):
    if code is None:
        return False
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def extract_ast_features(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    features = { 'for_loops': 0, 'while_loops': 0, 'if_statements': 0, 'function_calls': 0, 'list_comprehensions': 0, 'recursion': 0, 'node_count': 0 }
    function_names = set()
    for node in ast.walk(tree):
        features['node_count'] += 1
        if isinstance(node, ast.For):
            features['for_loops'] += 1
        elif isinstance(node, ast.While):
            features['while_loops'] += 1
        elif isinstance(node, ast.If):
            features['if_statements'] += 1
        elif isinstance(node, ast.Call):
            features['function_calls'] += 1
            if isinstance(node.func, ast.Name):
                function_names.add(node.func.id)
        elif isinstance(node, ast.ListComp):
            features['list_comprehensions'] += 1
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in function_names:
            features['recursion'] = 1
            break
    return features


def structural_similarity(generated_features, reference_features):
    if generated_features is None or reference_features is None:
        return None
    values = []
    for key in reference_features.keys():
        g = generated_features.get(key, 0)
        r = reference_features.get(key, 0)
        ma = max(g, r, 1)
        values.append(1 - abs(g - r) / ma)
    return sum(values) / len(values)


def evaluate_code(generated_code, test_source, entry_point):
    if generated_code is None:
        return {'syntax_valid': False, 'passed_tests': False, 'error_type': 'missing_output'}
    try:
        ast.parse(generated_code)
    except SyntaxError:
        return {'syntax_valid': False, 'passed_tests': False, 'error_type': 'syntax_error'}
    namespace = {}
    try:
        exec(generated_code, namespace)
        exec(test_source, namespace)
        if entry_point not in namespace or not callable(namespace[entry_point]):
            return {'syntax_valid': True, 'passed_tests': False, 'error_type': 'missing_function'}
        if 'check' not in namespace or not callable(namespace['check']):
            return {'syntax_valid': True, 'passed_tests': False, 'error_type': 'missing_test'}
        namespace['check'](namespace[entry_point])
        return {'syntax_valid': True, 'passed_tests': True, 'error_type': None}
    except AssertionError:
        return {'syntax_valid': True, 'passed_tests': False, 'error_type': 'failed_tests'}
    except Exception as exc:
        return {'syntax_valid': True, 'passed_tests': False, 'error_type': 'runtime_error', 'traceback': traceback.format_exc()}


def generate_code(prompt, model_name):
    try:
        client = Groq(api_key=GROQ_API_KEY)
        start = time.perf_counter()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        elapsed = time.perf_counter() - start
        raw_output = response.choices[0].message.content
        return {
            'raw_output': raw_output,
            'clean_output': extract_python_code(raw_output),
            'generation_seconds': round(elapsed, 3)
        }
    except Exception as exc:
        return {'raw_output': None, 'clean_output': None, 'generation_seconds': None, 'error': str(exc)}


def main():
    output = {
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'models': list(MODELS.keys()),
        'variations': VARIATIONS,
        'problem_ids': [p['id'] for p in PROBLEMS],
        'entries': []
    }

    ref_features = {p['id']: extract_ast_features(p['ref']) for p in PROBLEMS}
    total = len(MODELS) * len(VARIATIONS) * len(PROBLEMS) * 2
    count = 0

    for model_key, model_name in MODELS.items():
        for variation in VARIATIONS:
            for problem in PROBLEMS:
                prompt = problem['prompts'][variation]
                for run_id in range(2):
                    count += 1
                    print(f'[{count}/{total}] {model_key} {variation} {problem["id"]} run={run_id}')
                    result = generate_code(prompt, model_name)
                    clean = result.get('clean_output')
                    eval_result = evaluate_code(clean, problem['test'], problem['entry'])
                    gen_feats = extract_ast_features(clean)
                    sim = structural_similarity(gen_feats, ref_features[problem['id']])
                    output['entries'].append({
                        'model': model_key,
                        'variation_type': variation,
                        'problem_id': problem['id'],
                        'run_id': run_id,
                        'raw_output': result.get('raw_output'),
                        'clean_output': clean,
                        'generation_seconds': result.get('generation_seconds'),
                        'syntax_valid': eval_result['syntax_valid'],
                        'passed_tests': eval_result['passed_tests'],
                        'instruction_compliance': instruction_compliance(result.get('raw_output')),
                        'structural_similarity': sim,
                        'error_type': eval_result.get('error_type')
                    })
                    time.sleep(1.0)

    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(f'Wrote {OUTPUT_PATH.resolve()}')


if __name__ == '__main__':
    main()
