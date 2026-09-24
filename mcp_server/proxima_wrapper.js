#!/usr/bin/env node
// Wrapper around Proxima MCP server to automatically map `query` to `message`
// for ask_perplexity and other chat tools so tool validation never fails.

import { spawn } from 'child_process';
import readline from 'readline';

const targetScript = 'C:/Program Files/Proxima/resources/app.asar.unpacked/src/mcp/index.js';

const child = spawn(process.execPath, [targetScript], {
    stdio: ['pipe', 'pipe', 'inherit'],
    env: process.env
});

const rlIn = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: false });
const rlChild = readline.createInterface({ input: child.stdout, terminal: false });

// Forward child stdout to process stdout, augmenting tool schemas
rlChild.on('line', (line) => {
    try {
        const json = JSON.parse(line);
        if (json.result && Array.isArray(json.result.tools)) {
            for (const t of json.result.tools) {
                if ((t.name === 'ask_perplexity' || t.name === 'ask_chatgpt' || t.name === 'ask_claude' || t.name === 'ask_gemini') && t.inputSchema) {
                    if (t.inputSchema.properties) {
                        t.inputSchema.properties.query = {
                            type: 'string',
                            description: 'Alternative query parameter for message'
                        };
                    }
                }
            }
            process.stdout.write(JSON.stringify(json) + '\n');
            return;
        }
    } catch (e) {}
    process.stdout.write(line + '\n');
});

// Intercept stdin to child, ensuring `message` is set if `query` is passed
rlIn.on('line', (line) => {
    try {
        const json = JSON.parse(line);
        if (json.method === 'tools/call' && json.params) {
            const toolName = json.params.name;
            if (toolName === 'ask_perplexity' || toolName === 'ask_chatgpt' || toolName === 'ask_claude' || toolName === 'ask_gemini') {
                const args = json.params.arguments || {};
                if (!args.message && args.query) {
                    args.message = args.query;
                }
            }
        }
        child.stdin.write(JSON.stringify(json) + '\n');
    } catch (e) {
        child.stdin.write(line + '\n');
    }
});

child.on('exit', (code) => {
    process.exit(code || 0);
});
