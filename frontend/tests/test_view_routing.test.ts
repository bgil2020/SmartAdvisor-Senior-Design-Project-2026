import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { pathForView, viewFromPath } from '../src/utils/viewRouting.ts';

describe('application view routing', () => {
  it('makes the polished welcome screen the default', () => {
    assert.equal(viewFromPath('/'), 'welcome');
    assert.equal(viewFromPath('/unknown'), 'welcome');
  });

  it('restores Forms and Chatbot views from direct URLs', () => {
    assert.equal(viewFromPath('/forms'), 'forms');
    assert.equal(viewFromPath('/forms/'), 'forms');
    assert.equal(viewFromPath('/chatbot'), 'chat');
    assert.equal(viewFromPath('/chat'), 'chat');
  });

  it('uses stable canonical paths for navigation and refreshes', () => {
    assert.equal(pathForView('welcome'), '/');
    assert.equal(pathForView('forms'), '/forms');
    assert.equal(pathForView('chat'), '/chatbot');
  });
});
