with open('frontend/src/pages/TerminalPage.jsx', 'rb') as f:
    content = f.read()
content_str = content.decode('utf-8', errors='replace')
content_str = content_str.replace('export default function NSETradingTerminal', 'export default function TerminalPage')
with open('frontend/src/pages/TerminalPage.jsx', 'w', encoding='utf-8') as f:
    f.write(content_str)
