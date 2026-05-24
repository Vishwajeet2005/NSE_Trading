import json
with open('C:\\Users\\vishw\\.gemini\\antigravity\\brain\\aba86f97-a8ef-41fc-8a16-d0e05bf8b775\\.system_generated\\logs\\transcript.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in reversed(lines):
    try:
        data = json.loads(line)
        if 'tool_calls' in data:
            for call in data['tool_calls']:
                if call.get('name') == 'default_api:write_to_file':
                    args = call.get('arguments', {})
                    if 'NSETradingTerminal.jsx' in args.get('TargetFile', ''):
                        print('Found write_to_file for NSETradingTerminal.jsx')
                        with open('restored_terminal.jsx', 'w', encoding='utf-8') as out:
                            out.write(args['CodeContent'])
                        exit(0)
    except Exception as e:
        pass
print('Not found')

