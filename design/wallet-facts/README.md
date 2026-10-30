# Wallet Facts

A concept, not a feature yet. It's a way to explain wallet hygiene with a format people already know
how to read: a nutrition label. The mockups are in [wallet-facts.html](wallet-facts.html). Open it in
a browser.

## The idea

A browser wallet, a phone wallet and a hardware wallet are one thing in different wrappers: a single
secret. Each copy of that secret is a backup, and each copy is something to steal. With one key you
can only trade the risk of losing it against the risk of having it stolen. A multisig is the one
setup that gets out of that trade.

A label puts the few facts that matter in big type, the breakdown under them, and the trace details
at the bottom:

- **Serving size.** The kind of money the setup is made for.
- **Keys to move money.** The biggest number. One key means one mistake can be the whole balance.
- **Copies of the key**, and **key types**:
  - **Sealed**: born in a chip, one copy, nothing to leak and nothing to restore. A PicoQuorum key,
    a wedgie.
  - **Seed words**: twelve or twenty-four words. Every copy is the whole key.
  - **Synced**: a passkey copied by Apple or Google. No seed phrase, and the backup is your account.
- **Exposure and % at risk.** For each kind of attack or loss: how easy it is (a rough judgment),
  and how much of the balance one incident takes. For any single-key wallet, every attack that works
  takes 100%. That column is the lesson.
- **Trace amounts.** The secure element, whether the key can leave, whether the device checks the
  hash itself, whether you can verify the build.
- **Numbered circles** on a row point to real incidents where that row happened, with sources:
  Binance's hot wallets and Polymarket (both 29 October 2026, early reports), EIP-7702 delegation
  drains, Bybit, Radiant, WazirX, Ledger Connect Kit, seed phrases in LastPass vaults, stolen
  iPhones with their passcodes, and a kidnapping for ransom.
- **Ingredients**, everything you trust in order of how much, and **Contains**: "Contains: seeds."

Above the labels, one chart: how hard each setup is to steal against how hard it is to lose. Every
single-key setup sits near one diagonal. The 2-of-3 Safe is the only one off it.

The five mockups are a browser extension wallet, a hardware wallet with a paper seed, a synced
passkey alone, a sealed chip key alone (with a warning: no backup), and a 2-of-3 Safe held by three
people.

The Safe label shows a real limit too, and three of the incidents (Bybit, Radiant, WazirX) were
multisigs that hit it. If two of its owners sign what the same web page shows them,
a lying page gets both signatures. The console only helps when it is one of the two. That is the
governance rule in another form: no technology, and no person, holds a threshold's worth of keys.

## Instant Wallet

[Instant Wallet](https://github.com/clawdbotatg/instant-wallet) keeps one Safe address while you add
keys: a Face ID passkey, then your own recovery, then a wedgie. A label fits that ladder. The page
sketches a small front-of-box panel per rung, with three numbers (keys for a big move, what a stolen
phone takes, what happens if you lose the phone) and the full label behind it.

If both projects want this, the useful shared piece is the data, not the drawing: one small
description of a setup (its keys, their types and copies, the threshold, limits and delays) that
either app can turn into a label. That's not built.

## Open questions

- The exposure levels are judgments. They need sources, or a short rule for each level.
- A label per product, or per setup? This draft labels setups.
- Where it lives once it's real: here, in Instant Wallet, or on a small page both link to.
