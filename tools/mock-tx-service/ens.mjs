// ENS for tools/fw book: a name or an address, resolved both ways on Ethereum mainnet, so the
// owner sees exactly what goes into the console's QUORUM_BOOK before typing "yes". The console
// itself never asks ENS anything: a name on its screen is one pinned here.
//
//   resolve("vitalik.eth") -> { name, address, reverse, agrees }
//   resolve("0xd8dA...")   -> { name (the address's primary name, or null), address, reverse, agrees }
// agrees: the name resolves to the address AND the address's primary name is the name. A name that
// only resolves one way can still be pinned, but it is said plainly.
import { createPublicClient, getAddress, http, isAddress } from "viem";
import { mainnet } from "viem/chains";
import { normalize } from "viem/ens";

const RPC = process.env.ETH_RPC || "https://ethereum-rpc.publicnode.com";

export async function resolve(what) {
  const client = createPublicClient({ chain: mainnet, transport: http(RPC) });
  if (isAddress(what)) {
    const address = getAddress(what);
    const reverse = await client.getEnsName({ address });
    const forward = reverse ? await client.getEnsAddress({ name: normalize(reverse) }) : null;
    return { name: reverse, address, reverse, agrees: !!forward && forward.toLowerCase() === address.toLowerCase() };
  }
  const name = normalize(what);
  const address = await client.getEnsAddress({ name });
  if (!address) return { name, address: null, reverse: null, agrees: false };
  const reverse = await client.getEnsName({ address });
  return { name, address, reverse, agrees: reverse === name };
}
