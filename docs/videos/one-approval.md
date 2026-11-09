# 6. One approval, start to finish

*Draft script, 2026-11-09. Not recorded.*

| | |
|---|---|
| for | everyone: this is the demo |
| length | about 2:00 (230 words, with room for the screen) |
| the one idea | An approval is a thing you do with your hands: read every page, check the code with whoever proposed it, hold Sign. |

Screen and hands, with little talk. Record it on a testnet Safe, or on the emulator
(`tools/quorum e2e`). The shots in [quorum-ui/](../quorum-ui/README.md) show each screen.

## Script

*Shows: the app, a new transaction: send 0.05 ETH to Carol.*

Alice wants to pay Carol from the family Safe. It is a two-of-three. She proposes the payment and
signs it with her own wallet. That is one approval of two.

*Shows: the review, with its verify code and picture.*

The app shows her a verify code: the last eight characters of the transaction's hash, and a small
picture made from it. She sends the code to Bob.

*Shows: Bob's console, its home screen: one transaction waiting.*

Bob's console is another owner. The payment turns up in its queue.

*Shows: the summary page: "Send 0.05 ETH to Carol. 1 of 2 signed. Yours makes it 2 of 2."*

The console says what it does, in plain words: what moves, who gets it, who has signed.

*Shows: paging through. The verify page.*

Bob pages through every screen. One of them has the verify code. The console worked it out itself,
from the fields it just showed him. It matches the one Alice sent.

*Shows: a different transaction, a red page: add owner.*

If this had been a change to the Safe's owners, the page would be red all over.

*Shows: a thumb on Sign, the bar filling. Then let go early: the bar empties.*

Sign only works now that he has seen every page. He holds it for two seconds. If he lets go early,
nothing is signed.

*Shows: the thumb holds to the end, and the console says it is signed.*

The key in the console signs the hash. Two of two.

*Shows: the app's queue: every confirmation ticked, then Execute.*

Back in the app, anyone can finish it. The app checks every confirmation itself, tries the
transaction against the chain, and sends it.

*Shows: Carol's balance going up. Then the Reject button on the console.*

And if something looks wrong at any step, Reject is one press.

*Shows: picoquorum.app/console.*

You can do all of this in your browser, with a passkey as the key. Picoquorum is open source and
experimental.

## Check before recording

- The verify code is the hash's last eight characters and its blockie, in the app and on the
  console ([README](../../README.md#2-a-simple-console-that-checks-on-its-own)).
- Hold times: two seconds, three when a page is red ([SECURITY.md](../SECURITY.md)).
- "Anyone can finish it": executing needs a wallet to pay gas, not an owner's key. The app
  simulates first ([web/README.md](../../web/README.md), Execute).
- The wording on each screen changes with the firmware. Record from the release named in the
  video's description, and name it by its fingerprint.
- In the browser the computer draws the screen, and the passkey's prompt never shows the
  transaction. If the browser console is shown, say that the hardware console is the stronger
  owner ([guide/BROWSER.md](../guide/BROWSER.md)).
- Testnet only on screen. No API key, Wi-Fi name or password in any frame.

## For X

> One Safe approval, start to finish, in two minutes.
>
> Read every page. Check the code with whoever proposed it. Hold Sign for two seconds. Let go early
> and nothing is signed.
>
> picoquorum.app/learn

The cut: from Bob's home screen to "Two of two", about 50 seconds, no voice needed.
