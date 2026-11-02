// The verify code as an errand, the console's firmware/phrase.py in JS: the hash's last 4 bytes pick
// a name, a thing, an item and a when, each from a list of 256. Same 32 bits as the code. test.mjs
// checks these lists against the console's, word for word.
const NAMES = (
  "Abby|Adam|Ahmed|Aisha|Alan|Alice|Amir|Amy|Andre|Angela|Anika|Archie|Arjun|Arthur|Astrid|Audrey|" +
  "Barney|Beatrice|Beau|Benny|Bernard|Bianca|Boris|Brenda|Brody|Bruno|Caleb|Camila|Carlos|Carmen|" +
  "Cecil|Chandra|Charlie|Chester|Chloe|Clara|Clive|Colin|Connor|Cora|Curtis|Daisy|Dakota|Dale|Dana|" +
  "Daphne|Darius|Deepak|Delia|Derek|Diego|Dolores|Doug|Duncan|Edgar|Edith|Eduardo|Elena|Eli|Elsa|" +
  "Emeka|Enzo|Esther|Ethan|Eugene|Eva|Fatima|Felix|Fern|Fiona|Floyd|Frances|Frank|Freya|Gabe|Gary|" +
  "Gemma|Georgia|Gideon|Gina|Gloria|Gordon|Grace|Gus|Hamid|Hank|Hannah|Harold|Harvey|Hattie|Hazel|" +
  "Hector|Helga|Hiro|Hugo|Ian|Ibrahim|Ida|Igor|Imani|Ingrid|Irene|Iris|Isaac|Ivan|Ivy|Jacob|Jade|" +
  "Jamal|Janet|Jasper|Javier|Jenny|Jerome|Joanna|Joel|Jorge|Josie|Juan|Judith|Julian|Kai|Kayla|" +
  "Keith|Kenji|Kevin|Kira|Kofi|Lars|Laura|Lena|Leo|Lewis|Lila|Lionel|Lola|Lorenzo|Lucy|Luis|Luke|" +
  "Mabel|Malik|Marcus|Margot|Maria|Marvin|Mateo|Maxine|Megan|Miguel|Milo|Miriam|Molly|Morgan|Moses|" +
  "Mustafa|Nadia|Naomi|Nathan|Neil|Nico|Nina|Noah|Nora|Norman|Olga|Oliver|Omar|Opal|Oscar|Otis|" +
  "Owen|Pablo|Paloma|Patrick|Paula|Pedro|Penny|Percy|Petra|Phoebe|Pierre|Priya|Quentin|Quinn|" +
  "Rachel|Rafael|Rahul|Ralph|Ramona|Raymond|Rebecca|Reggie|Rhonda|Rita|Robin|Rocco|Roland|Rosa|" +
  "Rufus|Rupert|Ruth|Sabrina|Sally|Samir|Sandra|Santiago|Sasha|Selma|Sergei|Shirley|Silas|Simone|" +
  "Sofia|Stanley|Stella|Sunil|Susan|Sven|Sylvia|Tamara|Tariq|Teresa|Theo|Thomas|Tilly|Tobias|" +
  "Trevor|Tristan|Tyrone|Ulrich|Uma|Ursula|Valerie|Vera|Victor|Vikram|Vince|Viola|Walter|Wanda|" +
  "Warren|Wendy|Wesley|Wilbur|Willa|Winston|Wolfgang|Xavier|Yara|Yusuf|Yvonne|Zack|Zara|Zelda|Zoe").split("|");

const THINGS = (
  "amber|antique|azure|bamboo|beaded|beige|big|birch|black|blue|borrowed|brass|bright|broken|" +
  "bronze|brown|bulky|bumpy|burgundy|butter|camo|canvas|caramel|cardboard|carved|cedar|ceramic|" +
  "charcoal|checkered|cherry|chipped|chocolate|chrome|cinnamon|clay|clean|clunky|cobalt|cocoa|" +
  "copper|coral|cork|cotton|cozy|cracked|cranberry|cream|crimson|crooked|crystal|curved|cyan|dark|" +
  "deluxe|denim|dented|dirty|double|dull|dusty|eggplant|electric|emerald|enamel|faded|fancy|felt|" +
  "flat|flimsy|floral|fluffy|foam|folding|frayed|frosted|fuchsia|fuzzy|giant|glass|glazed|glossy|" +
  "gold|granite|greasy|green|grey|gritty|handmade|heavy|hefty|homemade|honey|huge|indigo|iron|" +
  "ivory|jumbo|junky|khaki|knotted|lace|lacquered|large|lavender|leaky|leather|lemon|lightweight|" +
  "lilac|lime|linen|little|long|loose|lucky|lumpy|magenta|magnetic|mahogany|maple|marble|maroon|" +
  "matte|mauve|mesh|messy|metal|mint|mirrored|modern|mossy|mottled|muddy|mustard|musty|narrow|navy|" +
  "neon|new|nickel|noisy|nylon|oak|ochre|oily|old|olive|orange|ornate|oval|padded|paper|pastel|" +
  "patched|peach|pearl|pewter|pine|pink|plaid|plain|plastic|plum|polished|polka dot|portable|" +
  "pumpkin|purple|quilted|rainbow|rattan|red|retro|rickety|rough|round|rubber|rugged|rusty|sage|" +
  "salmon|sandy|satin|scarlet|scratched|scuffed|secondhand|sepia|shabby|shaggy|shiny|short|silk|" +
  "silver|slate|sleek|slim|small|smoky|smooth|soft|solid|spare|sparkly|speckled|spiral|spongy|" +
  "spotted|square|squeaky|steel|sticky|stone|striped|stubby|sturdy|suede|swirly|tall|tan|tangerine|" +
  "tarnished|tartan|taupe|thick|thin|tinted|tiny|titanium|torn|toy|travel|tropical|turquoise|tweed|" +
  "twisted|vanilla|velvet|vintage|vinyl|violet|walnut|waterproof|waxed|white|wicker|wide|wireless|" +
  "wiry|wobbly|wonky|wooden|woolen|wrinkled|yellow|zinc").split("|");

const ITEMS = (
  "accordion|air pump|alarm clock|anchor|apron|armchair|backpack|banjo|barrel|basket|bathmat|" +
  "beach ball|beanbag|bedspread|bench|bicycle|bike lock|bike pump|binoculars|bird feeder|birdbath|" +
  "birdcage|birdhouse|blanket|blender|bookcase|bookend|boombox|bottle|bowl|bracelet|briefcase|" +
  "broom|bucket|bunk bed|cabinet|cake stand|calendar|camera|candle|canoe|canteen|card table|carpet|" +
  "cart|casserole dish|cello|chair|chandelier|cheese grater|chess set|clipboard|coat rack|" +
  "coffee maker|coffee table|colander|comforter|compass|cookie jar|cooler|corkboard|crate|crib|" +
  "crockpot|cuckoo clock|cupboard|curtain|cushion|cutting board|dartboard|deck chair|desk|" +
  "desk lamp|dish rack|dog bed|doghouse|dollhouse|doormat|drawer|dresser|drill|drum|dumbbell|duvet|" +
  "easel|egg timer|extension cord|fan|faucet|fiddle|fishing rod|flashlight|flower pot|fondue pot|" +
  "footstool|frying pan|futon|garden hose|globe|goldfish bowl|grill|guitar|hair dryer|hammer|" +
  "hammock|hamper|hat box|headboard|heater|high chair|hockey stick|hot plate|humidifier|" +
  "ice cream maker|ironing board|jewelry box|jigsaw puzzle|juicer|jukebox|kayak|kettle|keyboard|" +
  "kite|ladder|lamp|lampshade|lantern|laundry basket|lava lamp|lawn chair|lawnmower|leaf blower|" +
  "letter opener|lunchbox|magazine rack|mailbox|mandolin|mattress|microwave|mirror|mixer|mop|mug|" +
  "music stand|nightstand|ottoman|oven mitt|paddle|paint roller|piano|picnic basket|picnic table|" +
  "picture frame|piggy bank|pillow|pinball machine|pitcher|plant stand|planter|platter|pogo stick|" +
  "pool table|popcorn maker|pressure cooker|printer|punch bowl|quilt|radio|rain barrel|rake|" +
  "recliner|record player|rice cooker|rocking chair|rolling pin|rowing machine|rug|saddle|" +
  "salad bowl|sandbox|saucepan|saw|scale|scarf|scooter|screen door|sewing machine|shelf|shoe rack|" +
  "shovel|shower curtain|sideboard|skateboard|sled|sleeping bag|snow shovel|sofa|space heater|" +
  "spatula|speaker|spice rack|sprinkler|stepladder|stereo|stool|stroller|suitcase|sunhat|surfboard|" +
  "sweater|swing|table|tablecloth|tape measure|teapot|telescope|tent|thermos|toaster|tool chest|" +
  "toolbox|towel rack|toy box|trampoline|tray|treadmill|tricycle|tripod|trombone|trophy|trowel|" +
  "trumpet|trunk|tuba|typewriter|ukulele|umbrella|umbrella stand|vacuum|vase|waffle iron|wagon|" +
  "wall clock|wardrobe|washboard|weather vane|wheelbarrow|whisk|wind chime|window box|wine rack|" +
  "wok|workbench|wreath|xylophone|yoga mat").split("|");

const WHEN = (
  "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Monday morning|Monday afternoon|" +
  "Monday evening|Monday night|Tuesday morning|Tuesday afternoon|Tuesday evening|Tuesday night|" +
  "Wednesday morning|Wednesday afternoon|Wednesday evening|Wednesday night|Thursday morning|" +
  "Thursday afternoon|Thursday evening|Thursday night|Friday morning|Friday afternoon|" +
  "Friday evening|Friday night|Saturday morning|Saturday afternoon|Saturday evening|Saturday night|" +
  "Sunday morning|Sunday afternoon|Sunday evening|Sunday night|next Monday|next Tuesday|" +
  "next Wednesday|next Thursday|next Friday|next Saturday|next Sunday|one o'clock|two o'clock|" +
  "three o'clock|four o'clock|five o'clock|six o'clock|seven o'clock|eight o'clock|nine o'clock|" +
  "ten o'clock|eleven o'clock|twelve o'clock|half past one|half past two|half past three|" +
  "half past four|half past five|half past six|half past seven|half past eight|half past nine|" +
  "half past ten|half past eleven|half past twelve|quarter past one|quarter past two|" +
  "quarter past three|quarter past four|quarter past five|quarter past six|quarter past seven|" +
  "quarter past eight|quarter past nine|quarter past ten|quarter past eleven|quarter past twelve|" +
  "quarter to one|quarter to two|quarter to three|quarter to four|quarter to five|quarter to six|" +
  "quarter to seven|quarter to eight|quarter to nine|quarter to ten|quarter to eleven|" +
  "quarter to twelve|January|February|March|April|May|June|July|August|September|October|November|" +
  "December|early January|early February|early March|early April|early May|early June|early July|" +
  "early August|early September|early October|early November|early December|late January|" +
  "late February|late March|late April|late May|late June|late July|late August|late September|" +
  "late October|late November|late December|the end of January|the end of February|" +
  "the end of March|the end of April|the end of May|the end of June|the end of July|" +
  "the end of August|the end of September|the end of October|the end of November|" +
  "the end of December|tomorrow|tomorrow morning|tomorrow night|tonight|this afternoon|" +
  "this evening|midnight|the weekend|next weekend|the long weekend|next week|the week after|" +
  "next month|next year|after breakfast|after lunch|after dinner|after school|after work|" +
  "after church|after practice|after the game|after the meeting|after the wedding|after the move|" +
  "after the trip|after the storm|after the holidays|after payday|payday|the first of the month|" +
  "the holidays|spring break|spring|summer|fall|winter|Christmas|Christmas Eve|Easter|Halloween|" +
  "Thanksgiving|New Year's|New Year's Eve|Labor Day|Memorial Day|the Fourth|Valentine's Day|" +
  "Mother's Day|Father's Day|the birthday party|the reunion|the barbecue|the recital|the yard sale|" +
  "the open house|the bake sale|the potluck|graduation|the game|the parade|the fair|" +
  "the camping trip|the road trip|the dentist|the vet|the plumber|the inspection|the renovation|" +
  "the harvest|the first frost|the first snow|the thaw|garbage day|bin day|laundry day|the cleanup|" +
  "the next full moon|sunrise|sunset|dawn|dusk|lunchtime|dinnertime|bedtime|the morning|" +
  "the afternoon|the evening|later|after the kids are asleep|the end of the week|" +
  "the end of the month|mid-week|the next rainy day|the next sunny day|our next visit|" +
  "your next visit|we get back|you get back|the baby's nap|the bus comes|the mail comes|" +
  "the rain stops|the paint dries|the tide goes out|kickoff|halftime|the day after tomorrow|" +
  "the weekend after|the end of the day|the end of the year|after the concert|the concert|" +
  "the wedding|the school play|the first warm day|the lunch break|the first of next month").split("|");

export const LISTS = [NAMES, THINGS, ITEMS, WHEN];
// hash: 0x hex. -> [name, thing, item, when]
export const words = (hash) => LISTS.map((l, i) => l[parseInt(hash.slice(-8).slice(2 * i, 2 * i + 2), 16)]);
export const phrase = (hash) => {
  const [name, thing, item, when] = words(hash);
  return `Tell ${name} the ${thing} ${item} can wait till ${when}.`;
};
