# Governance: the project Safe

> **Plan (updated 2026-10-06).** The project Safe doesn't exist on chain yet. The code is ready for it:
> - release approvals, in the console, the app and `tools/release`;
> - the `"project"` slot in `firmware/quorum_cfg.py`.
>
> Done: the name, **picoquorum.eth**, is registered from the hardware wallet; the domains
> picoquorum.app, .com, .org and .dev are bought; the repository is public. What exists today:
> [STATUS.md](STATUS.md).

PicoQuorum's own decisions should go through the same kind of Safe it secures, approved on the same
consoles. Those decisions are which releases the project stands behind, who controls its name, and
later its website and funds. One Safe holds them. You hold it alone at first, and it is built to be
handed over.

## The shape

**One Safe, at the same address on Ethereum and Base.**

| | Ethereum (canonical) | Base |
|---|---|---|
| Owns the ENS name | yes | — |
| Approves releases (SignMessageLib), what the app checks | yes | — |
| Day-to-day: test Safes' gas, small payments, later grants | — | yes |

**Owners to start: 2 of 3, three technologies, all yours.**

1. **A Trust M console key.** Its owner is its passkey-signer proxy, the same address on every chain.
2. **A hardware wallet** (an ordinary EOA). It can also pay for and send transactions, which a P-256
   key can't yet (`HEGOTA-WATCH.md`).
3. **Your passkey**, through the browser console (`EMU-WEB.md`) or on a YubiKey. Its owner address
   comes from the same factory.

Two of three means losing one key costs nothing, and one compromised technology can't act alone.
That's the rule as owners are added: **no technology, and no person, holds a threshold's worth of
keys.**

## The same address on both chains

A Safe's address follows from its factory, singleton, setup data and salt. Use the same four on both
chains and you get the same address.
- **Create it** on Ethereum in Safe{Wallet}, then use **Add another network → Base**. That
  replays the same setup.
- **Check the two addresses match before using it.** Safe 1.4.1's L1 and L2 singletons are both
  deployed on both chains, so a mismatch is easy if one side picks the other singleton.
- **Settings:** Safe 1.4.1, the default CompatibilityFallbackHandler 1.4.1 (release approvals need
  it), no modules, no guard.
- **Deploy each P-256 owner's signer proxy on both chains,** from the key's page in the app
  (`tools/quorum live enroll`). A passkey owner's signature only verifies where its proxy exists.

**Owners and threshold live separately on each chain.** Make every owner change on both chains the
same day. `tools/quorum governance check` (planned) will read both and report any drift. Until
then, compare the two Safes' owners and thresholds in the app.

## Releases

The project Safe approves each release on Ethereum (`RELEASES.md`, *Approval by the project Safe*):
1. `tools/release approval` prints the transaction: a delegatecall to Safe's SignMessageLib, with
   the release in a short note.
2. Propose it from the app's **Releases** page. Each owner's console shows **Approve release …**,
   with the firmware's blockie and whether it is the release that console runs.
3. Once executed, `isValidSignature(D, "0x")` on the Safe says so for good, even after owners
   change. The Releases page shows **Approved by the project Safe**.

Setting `"project": {"chainId": 1, "address": "0x…"}` in `firmware/quorum_cfg.py`, in a reviewed
commit, is what turns those checks on.

Git tags stay signed by maintainers' SSH keys (`.github/allowed_signers`). The tag says who cut a
release. The Safe says the project stands behind it, and the Safe is what people check.

## ENS

The name is **picoquorum.eth**, registered from the hardware wallet
`0x682De3ad16F47Acd01e97A73f1619be93672a9f3` until 2031-10-06 ([STATUS.md](STATUS.md#names-and-domains)).
1. **Keep it registered for a long term.** Anyone can renew a name, but an expired one can be taken:
   consider extending it to ten years.
2. **Make the Safe its owner and its manager** in the ENS app. If the name is wrapped, the Safe
   holds the wrapped name. From then on every change is a Safe transaction.
3. **Records** (ENS Public Resolver), set in one Safe transaction (`multicall`):
   - **`addr`:** Ethereum = the Safe; Base (coin type `0x80002105`) = the Safe.
   - **`url`:** the site, `https://picoquorum.app`.
   - **`text org.picoquorum.release`:** the latest approved release and its digest. A convenience
     only: the approval itself is on the Safe.
   - **Later, `contenthash`:** the IPFS CID of a release's `docs/` build. The site at
     `picoquorum.eth.limo` is then whatever the owners approved, not whatever the server sends.

**For the console:** today a resolver call is a contract call the console can't decode, so it shows
up red and unread. A firmware item to come: decode `setText`, `setAddr`, `setContenthash` and
`multicall` on the pinned Public Resolver, so ENS changes are clear-signed like everything else:
*Set picoquorum.eth url to …*.

## Handing it over

| Stage | Owners | Threshold | Who can act |
|---|---|---|---|
| Now | you: Trust M, hardware wallet, passkey | 2 of 3 | you |
| First co-maintainer | + their console key | 2 of 4 | you, or one of yours plus theirs |
| A real quorum | + a second co-maintainer, and a third technology for them | 3 of 5 | no single person |

- **Every step is a Safe transaction on both chains.** Owner and threshold changes show up red on
  the console, and every owner checks the new owner's address on their own screen.
- **Retire your extra keys as people join,** so the maintainer alone never holds a threshold.
- **Co-maintainers' SSH keys go into `.github/allowed_signers`** in a reviewed commit, so they can
  cut releases too. Approving releases stays with the Safe.

## The public repository

1. **Public, with its history** (2026-10). Before it went public, the picowallet-only files were
   removed and the licenses set (code MIT, hardware CERN-OHL-W-2.0, docs CC BY-SA 4.0; the name
   and mark reserved: [TRADEMARK.md](../TRADEMARK.md)).
2. **Build provenance.** `release.yml` adds `actions/attest-build-provenance` for the firmware
   zips and the web builds, checked with `gh attestation verify`. Anyone can also rebuild a tag
   and compare `BUILD.json`.
3. **A domain before passkeys hold value.** A passkey is tied to the site it was made for:
   - every Pages site under `jmcpheron.github.io` shares one;
   - moving later means new passkeys, which are owner changes.

   The domain is **picoquorum.app**: the site moves there once its DNS is set, and the project
   Safe's passkey is made there. picoquorum.com, .org and .dev only redirect to it, and
   `picoquorum.eth.limo` comes later, with a contenthash.
4. **Checking the live site.** What the browser runs is whatever the site sends, and a page can't
   vouch for itself. `.github/workflows/site-check.yml` checks it from outside:
   - every byte Pages serves, against `docs/` at the commit it deployed;
   - after every deploy and every six hours;
   - an issue opens on any difference.

   The app's Releases page says which release the page is, and whether this Safe approved it. With a
   public repository, anyone can run `tools/release check-site` themselves.

## First steps

1. Get the three owner addresses:
   - the Trust M key's, from its page in the app;
   - the passkey's, from the browser console's Chip page (key menu: your passkey);
   - the hardware wallet's.
2. Create the Safe on Ethereum (2 of 3), add Base, and check the addresses match.
3. Deploy each P-256 owner's signer proxy on both chains.
4. Commit the address as `quorum_cfg.py` `"project"`.
5. Hand picoquorum.eth to the Safe; set the records. (Registered 2026-10.)
6. Make the first release (`RELEASES.md`), then approve it from the consoles.
