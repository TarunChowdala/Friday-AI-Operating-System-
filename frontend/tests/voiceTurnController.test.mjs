import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/hooks/voiceTurnController.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { VoiceTurnController } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

function setup() {
  const calls = { bargeIn: 0, utterances: [] };
  const controller = new VoiceTurnController({
    onBargeIn: () => calls.bargeIn++,
    onUtterance: (audio) => calls.utterances.push(audio),
  });
  return { controller, calls };
}

test('sends one utterance after speech end and ignores a duplicate end', () => {
  const { controller, calls } = setup();
  const audio = new Float32Array(4000);
  controller.setMicEnabled(true);
  controller.onSpeechStart();
  controller.onSpeechEnd(audio);
  controller.onSpeechEnd(audio);
  assert.deepEqual(calls.utterances, [audio]);
  assert.equal(calls.bargeIn, 0);
});

test('barge-in waits for Silero real-speech confirmation and fires once', () => {
  const { controller, calls } = setup();
  controller.setMicEnabled(true);
  controller.setAssistantActive(true);
  controller.onSpeechStart();
  assert.equal(calls.bargeIn, 0);
  controller.onSpeechRealStart();
  controller.onSpeechRealStart();
  assert.equal(calls.bargeIn, 1);
  controller.onSpeechEnd(new Float32Array(4000));
  assert.equal(calls.utterances.length, 1);
});

test('does not interrupt or submit audio while mic is disabled', () => {
  const { controller, calls } = setup();
  controller.setAssistantActive(true);
  controller.onSpeechStart();
  controller.onSpeechRealStart();
  controller.onSpeechEnd(new Float32Array(4000));
  assert.equal(calls.bargeIn, 0);
  assert.equal(calls.utterances.length, 0);
});

test('ignores short segments and resets a candidate after a VAD misfire', () => {
  const { controller, calls } = setup();
  controller.setMicEnabled(true);
  controller.setAssistantActive(true);
  controller.onSpeechStart();
  controller.onMisfire();
  controller.onSpeechRealStart();
  controller.onSpeechEnd(new Float32Array(4000));
  controller.onSpeechStart();
  controller.onSpeechEnd(new Float32Array(1600));
  assert.equal(calls.bargeIn, 0);
  assert.equal(calls.utterances.length, 0);
});

test('a later utterance can interrupt a later assistant response', () => {
  const { controller, calls } = setup();
  controller.setMicEnabled(true);
  controller.setAssistantActive(true);
  controller.onSpeechStart();
  controller.onSpeechRealStart();
  controller.onSpeechEnd(new Float32Array(4000));
  controller.setAssistantActive(true);
  controller.onSpeechStart();
  controller.onSpeechRealStart();
  assert.equal(calls.bargeIn, 2);
});
