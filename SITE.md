# Proposed website text

## Portfolio entry

**Title:** The welfare cost of Proof of Work: Bitcoin and Ethereum

**Type and year:** Model calibration, 2026

Chiu & Koeppl measured the welfare cost of Bitcoin's Proof of Work with a model of how blockchains settle payments. I applied the same model to Ethereum and compared the two coins on the same year, using transfer sizes measured from public chain data. In 2020 Proof of Work cost about 0.74% of consumption for Bitcoin and 0.57% for Ethereum, mostly in mining, and the gap rests on Bitcoin's largest transfers.

Repository: https://github.com/atamalfuzi/pow_welfare_cost

## Project page

Figures are in `figures/`, in this order: `same_year.png`, `sensitivity.png`, `rewards.png`, `halvings.png`, `transfer_sizes.png`.

### The question

Chiu & Koeppl's model treats a Proof-of-Work blockchain as a payment system. Buyers wait for confirmations so that double-spending does not pay, and miners spend about what they earn. They used it to measure Bitcoin's welfare cost. I wanted to see what it says about Ethereum, which had much shorter blocks before it moved to staking in 2022.

### The result

In 2020, Bitcoin cost 0.74% of consumption and Ethereum 0.57%. Most of the cost is mining, which is close to miner revenue divided by transfer volume: 0.54% and 0.57%, about equal. The gap comes from waiting. Ethereum's large transfers wait minutes and Bitcoin's wait hours.

[`same_year.png`]

Ethereum is lower in all but one of the alternatives I tried, and in two of them the coins are within 0.01 points. Without Bitcoin's transfers of 1,000 BTC or more, many of which are probably not payments, the two coins are level. So Ethereum was somewhat cheaper in 2020, but the size of the gap is not settled.

[`sensitivity.png`]

### Rewards, fees and later years

Each extra point of fee share adds about a point of cost, and paying the same reward through fees or new coins makes almost no difference. Lower rewards cut the cost until waiting takes over. Bitcoin's cost fell to 0.56% in 2025 on blockchain.com's volume, from 1.01% in 2020 on the same measure. Further halvings help down to a subsidy of about 0.78 coins per block.

[`rewards.png`, `halvings.png`]

The model does not apply to Ethereum after the Merge, because its double-spend limit and mining cost come from a hash race. I give only a rough range for 2025, 0.01% to 0.10%, which does not come from the model.

### Data

Transfer sizes come from AWS's public blockchain tables, read with DuckDB without downloading them. Supply, issuance and fees come from Coin Metrics community data.

[`transfer_sizes.png`]
