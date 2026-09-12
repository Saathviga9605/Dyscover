export type SpeechPromptKind = 'word' | 'letter' | 'letter-pair' | 'sentence' | 'ran';

export interface SpeechLevel {
  name: string;
  subtitle: string;
  kind: SpeechPromptKind;
  pool: readonly string[];
  minTrials: number;
  hideAfterMs?: number;
  totalTimeMs?: number;
  distractionMode?: boolean;
  flashMode?: boolean;
  storyParts?: readonly string[];
}

export interface SpeechGameContent {
  id: string;
  title: string;
  description: string;
  levels: readonly SpeechLevel[];
}

export const SOUND_QUEST_ADVENTURE: SpeechGameContent = {
  id: 'sound-quest-adventure',
  title: 'Sound Quest Adventure',
  description: 'Read each word or sentence aloud to move the story forward.',
  levels: [
    {
      name: 'Level 1 — Sounds & Simple Words',
      subtitle: 'Identify beginning sounds and speak simple CVC words',
      kind: 'word',
      pool: ['cat', 'dog', 'pin', 'bat', 'mat', 'sit', 'top', 'run', 'bed', 'pig'],
      minTrials: 6,
    },
    {
      name: 'Level 2 — Word Pronunciation & Rhyming',
      subtitle: '2-syllable words, sound contrasts, and simple rhymes',
      kind: 'word',
      pool: ['rabbit', 'sunny', 'paper', 'tiger', 'pat bat', 'sip ship', 'cat hat', 'run fun'],
      minTrials: 6,
    },
    {
      name: 'Level 3 — Story Unlock',
      subtitle: 'Read short sentences aloud to unlock the story',
      kind: 'sentence',
      pool: [
        'The red fox ran home.',
        'A little puppy found a bone.',
        'Mina opens the magic gate.',
        'The yellow bird sang loudly.',
        'Sam carries a basket of apples.',
      ],
      minTrials: 5,
      storyParts: [
        'The map glows and the trail opens.',
        'A tiny bridge appears across the stream.',
        'The forest lights up with friendly fireflies.',
        'The hidden gate unlocks with a golden spark.',
        'The adventure ends with treasure and cheers.',
      ],
    },
  ],
};

export const LETTER_BUBBLE_POP: SpeechGameContent = {
  id: 'letter-bubble-pop',
  title: 'Letter Bubble Pop',
  description: 'Say the letters you see to pop the bubbles.',
  levels: [
    { name: 'Level 1 — Basic Letter Pop', subtitle: 'Normal letters appear and your child says the letter to pop it', kind: 'letter', pool: ['a', 'm', 'o', 's'], minTrials: 4 },
    { name: 'Level 2 — Confusing Letters Pop', subtitle: 'Say both similar letters shown together', kind: 'letter-pair', pool: ['b d', 'p q', 'm n', 'u v'], minTrials: 4 },
    { name: 'Level 3 — Rapid Pop', subtitle: 'Fast naming mode — say each letter or shape quickly', kind: 'ran', pool: ['b', 'triangle', 'q', 'circle', 'v', 'square', 'm', 'star'], minTrials: 6, hideAfterMs: 5000, totalTimeMs: 15000 },
  ],
};

export const MAZE_RUNNER_RUSH: SpeechGameContent = {
  id: 'maze-runner-rush',
  title: 'Maze Runner Rush',
  description: 'Name each word as it flashes on the path.',
  levels: [
    { name: 'Level 1 — Slow Flash Naming', subtitle: 'Slow images, letters, and words appear', kind: 'word', pool: ['apple', 'sun', 't', 'book', 'fish', 'car'], minTrials: 6, totalTimeMs: 18000 },
    { name: 'Level 2 — Rapid Naming Pathway', subtitle: 'Faster words with less answer time', kind: 'ran', pool: ['star', 'lamp', 'pen', 'goat', 'ring', 'tree'], minTrials: 6, hideAfterMs: 3000, totalTimeMs: 8000 },
    { name: 'Level 3 — Distraction Maze', subtitle: 'Flashing words under distraction', kind: 'word', pool: ['planet', 'window', 'basket', 'silver', 'garden', 'rocket'], minTrials: 6, hideAfterMs: 2500, totalTimeMs: 10000, distractionMode: true, flashMode: true },
  ],
};

export const SPEECH_GAME_CONTENTS: readonly SpeechGameContent[] = [SOUND_QUEST_ADVENTURE, LETTER_BUBBLE_POP, MAZE_RUNNER_RUSH];