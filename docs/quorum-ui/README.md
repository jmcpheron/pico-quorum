# The console's Safe approval screens: a walkthrough

Every picture here is the real firmware (`firmware/quorum.py`, `quorum_ui.py`, `decode.py`) running
in the emulator against a simulated Safe on the laptop (`tools/quorum`). The emulator's screen is
pixel-for-pixel the Pico's 240×240 panel, shown here at 2×. `tools/quorum shots` regenerates every
image. Run it twice and you get the same bytes, so a changed image in a commit means the screen
changed.

**How to review from your phone:** comment on any line or image in the pull request, or edit the
[change requests](#change-requests) checklist at the bottom straight in GitHub. I pull before every
iteration and work through both.

## Iteration log

### Iteration 1 (2026-09-24): the first pass

**What's built:**
- **The queue:** the whole queue on one screen.
- **Review:** a summary page, one page per thing the transaction does (each call of a batch
  gets its own page), and red pages for anything that can take the Safe away from its owners.
- **Verify:** a page with the hash's last 8 characters to read out over the phone.
- **Signing:** hold A to sign, but only after every page has been seen.
- **Refusal:** the console refuses outright when the service lies.
- **On the laptop:** a 2-of-3 Safe with two simulated co-signers. It checks the chip's P-256
  signature independently and "executes" once there are enough approvals.

**Not yet:**
- No chain, and no Safe contracts.
- The signature is the chip's raw r‖s. How it gets packaged for the Safe (WebAuthn signer or
  ERC-1271) is still open.
- This key's owner address is a stand-in, `keccak(qx‖qy)`.
- Not yet run on the real Pico. That's the next step, with you at the device.

**Questions for you** (answer inline, in a PR comment, or in the change requests):
1. **Reject.** Y declines on this console only: the row shows NO, and the laptop logs it. Nothing
   goes to the Safe. Should Y also offer to sign an *on-chain rejection*? That's the Safe's real
   "no": an empty transaction that uses up the same number.
2. **Hold times.** 2 s normally, 3 s when any page is red. Too short, too long?
3. **The verify code** is the hash's last 8 characters, big (the Safe app's convention and the
   kickoff's). The full hash and its blockie sit right under it, because 8 characters alone can be
   ground out by an attacker. Enough, or should the whole hash be the big thing?
4. **Buttons.**
   - Home: A open, B owners, X chip map (LAB and snake are still in there).
   - Review: A sign, Y reject, B back, stick to page.

   Does B = back feel right, with Y reserved for reject?
5. **Unknown tokens** (a transfer of a token not in the list) are **yellow**, not red, with the
   amount in raw units. Should they be red?

## The setup

| | |
|---|---|
| **Safe** | FAMILY SAFE, `0x5afe…a11e`, on chain 31337 (LOCAL: nothing signed here is valid on a real chain) |
| **Owners** | ALICE and BOB (simulated, on the laptop) and THIS KEY (the chip), 2 of 3 must approve |
| **Buttons** | A (top, green) SIGN · B back / owners · X chip map · Y (bottom, red) REJECT · stick: pages |
| **Pinned** | the Safe, the chain, the names, the tokens and the batch contract live on the console (`firmware/quorum_cfg.py`). The transaction service is not trusted for any of it |

The demo queue: Alice sends ETH, a batch, Bob adds a stranger as an owner, a transaction the
service lies about, and a call nobody can decode.

## 1. The queue

<img src="shots/01-home.png" width="48%">

- The top strip is the chain: orange for LOCAL, blue for Base, purple for Base Sepolia.
- **Rows:**
  - `1/2` is approvals so far.
  - Red rows with `!` have at least one red page.
  - `REFUSED` rows can't be signed at all.
  - `YOU` means this key has signed; `NO` means it was rejected here.
- The footer shows which key is in the chip and whether the Safe counts it as an owner.
- The Pico's LED blinks while anything waits for this key.

## 2. A first approval: Alice sends Carol 0.05 ETH

| | |
|---|---|
| <img src="shots/02-approve-summary.png"> | <img src="shots/03-approve-send.png"> |
| **A on the row: the summary.** What it does, who has approved, and what your approval would do ("yours makes 2 of 2: ready"). SIGN is grey: 1 of 3 pages seen. | **Down: what it does.** The amount, the name from the address book, and the full address in 4-character chunks. The name is a hint; the address is what's signed. |
| <img src="shots/04-approve-every-page-first.png"> | <img src="shots/05-approve-hold.png"> |
| **A before the last page** jumps to the page you haven't seen and says why. This is the verify page: the hash was computed *here* from the fields on the pages before. Its last 8 characters are what you'd read to the proposer on a call. | **Hold A.** The bar fills over 2 s. Let go and nothing is signed. |
| <img src="shots/06-approve-signed.png"> | <img src="shots/07-approve-home-after.png"> |
| **Signed.** The chip signed the hash, and the laptop checked the P-256 signature against this key and counted it. 2 of 2, so the simulated Safe executes. | **Back home:** #0 is gone and the queue moves on to #1. |

## 3. A batch: two payments in one transaction

| | |
|---|---|
| <img src="shots/08-batch-summary.png"> | <img src="shots/09-batch-call-1.png"> |
| The summary lists every call. The batch contract (MultiSendCallOnly) is on the console's list, so its delegatecall is not a red flag. | Each call gets its own page… |
| <img src="shots/10-batch-call-2.png"> | <img src="shots/11-batch-verify.png"> |
| …with token amounts in the token's real decimals. | The one hash covers the whole batch. |

## 4. A red screen: Bob adds a stranger as an owner

| | |
|---|---|
| <img src="shots/12-owner-summary.png"> | <img src="shots/13-owner-red-page.png"> |
| Red text on the summary, and a banner: 1 red page, read it. | **The red page** is red all over. The thing at stake (the address that would get a vote) is in cyan, like the thing lost on the chip map's red PERMANENT screen. |
| <img src="shots/14-owner-let-go-early.png"> | <img src="shots/15-owner-hold-red.png"> |
| A red transaction needs **3 s**. Letting go at 2.3 s signs nothing. | The hold box says why it's longer. |

## 5. The service lies

The service shows "0.05 ETH to Carol" but asks for a signature over the hash of *5 ETH to a
stranger*. A console that signed the hash it was handed would approve the theft.

| | |
|---|---|
| <img src="shots/16-lie-refused.png"> | <img src="shots/17-lie-claimed.png"> |
| **REFUSED.** The console hashed the fields itself and got a different hash. Both are shown. | Down shows what the service *claims*, marked as a claim. |
| <img src="shots/18-lie-cant-sign.png"> | |
| A does nothing but say why. Y (reject) still works. | |

## 6. A call nobody described

| | |
|---|---|
| <img src="shots/19-unknown-summary.png"> | <img src="shots/20-unknown-red-page.png"> |
| Anything the console can't decode is red. | The function selector, the contract, and the calldata digest (ERC-8213), so it can be compared with what the proposer says they sent. |

## 7. Rejecting

<img src="shots/21-reject-home.png" width="48%">

Y on any review page: instant, no hold. The row shows `NO`, and the laptop's log says who rejected
it. It is not sent to the Safe (question 1 above).

## 8. More red screens

| | |
|---|---|
| <img src="shots/22-reds-home.png"> | <img src="shots/23-refund-red-page.png"> |
| A queue of the other red cases. | **A gas refund:** the Safe would pay whoever executes it, in USDC here, to an unknown address. |
| <img src="shots/24-delegatecall-red-page.png"> | <img src="shots/25-threshold-red-page.png"> |
| **Delegatecall** to a contract that isn't the known batch contract: it would run as the Safe. | **Threshold change** to 1: any one owner could then move everything. |
| <img src="shots/26-wrong-safe-refused.png"> | |
| A transaction for a **different Safe** slipped into this one's queue: refused. | |

## 9. Two proposals for one number

| | |
|---|---|
| <img src="shots/27-conflict-home.png"> | <img src="shots/28-conflict-summary.png"> |
| Alice proposes 1 ETH to Carol, and Bob proposes to reject it at the same number. Only one can run. | The summary says so. |
| <img src="shots/29-conflict-rejection-page.png"> | |
| The Safe's on-chain rejection, explained. | |

## 10. The rest

| | |
|---|---|
| <img src="shots/30-owners.png"> | <img src="shots/31-chip-map.png"> |
| **B from home:** the owners, in full. | **X from home:** the chip map, as before. LAB and snake are inside, and Y comes back. |
| <img src="shots/32-no-service.png"> | |
| **No service:** the error and the URL it tried. Everything local still works. | |

## Run it yourself

```sh
tools/quorum serve                 # the simulated Safe + a dashboard at http://localhost:8787
tools/quorum demo                  # the demo queue
EMU_APP=http://localhost:8787 tools/emu run quorum    # the console in the emulator, talking to it
tools/quorum confirm 1 --as bob    # a co-signer approves #1
tools/quorum status                # who has signed what
tools/quorum shots                 # regenerate every picture on this page
```

On the Pico, `secrets.py` gets `QUORUM_URL = "http://<this Mac's LAN IP>:8787"` (`tools/quorum ip`
prints the line).

## Change requests

Edit this list on GitHub: add a line, tick one off, or write under it. Each iteration starts here.

- [ ] (add yours)
