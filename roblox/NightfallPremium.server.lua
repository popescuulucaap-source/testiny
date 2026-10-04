-- Nightfall Premium Roblox receipt bridge
-- Put this Script in ServerScriptService in the Roblox experience used for Premium purchases.
-- IMPORTANT: replace the values below and keep the secret server-side.
local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")

local NIGHTFALL_URL = "https://testiny-7wuu.onrender.com"
local NIGHTFALL_SECRET = "REPLACE_WITH_ROBLOX_PREMIUM_SECRET"
local PREMIUM_30D_PRODUCT_ID = 0 -- replace with the Roblox Developer Product ID
local PREMIUM_90D_PRODUCT_ID = 0 -- replace with the Roblox Developer Product ID

local pendingClaimCodes = {}

local function postReceipt(receiptInfo, claimCode)
    local ok, response = pcall(function()
        return HttpService:RequestAsync({
            Url = NIGHTFALL_URL .. "/api/roblox/premium-receipt",
            Method = "POST",
            Headers = {
                ["Content-Type"] = "application/json",
                ["X-Nightfall-Roblox-Key"] = NIGHTFALL_SECRET,
            },
            Body = HttpService:JSONEncode({
                purchase_id = tostring(receiptInfo.PurchaseId),
                product_id = tostring(receiptInfo.ProductId),
                roblox_user_id = tostring(receiptInfo.PlayerId),
                claim_code = claimCode,
            }),
        })
    end)
    if not ok or not response.Success then
        warn("Nightfall Premium bridge failed:", response)
        return false
    end
    local data = HttpService:JSONDecode(response.Body)
    return data.ok == true
end

local function processReceipt(receiptInfo)
    local productId = tonumber(receiptInfo.ProductId)
    if productId ~= PREMIUM_30D_PRODUCT_ID and productId ~= PREMIUM_90D_PRODUCT_ID then
        return Enum.ProductPurchaseDecision.NotProcessedYet
    end

    local player = Players:GetPlayerByUserId(receiptInfo.PlayerId)
    if not player then
        return Enum.ProductPurchaseDecision.NotProcessedYet
    end

    local claimCode = pendingClaimCodes[player.UserId]
    if not claimCode then
        warn("Nightfall Premium purchase is waiting for a claim code. Player:", player.UserId)
        return Enum.ProductPurchaseDecision.NotProcessedYet
    end

    if postReceipt(receiptInfo, claimCode) then
        pendingClaimCodes[player.UserId] = nil
        return Enum.ProductPurchaseDecision.PurchaseGranted
    end

    return Enum.ProductPurchaseDecision.NotProcessedYet
end

MarketplaceService.ProcessReceipt = processReceipt

Players.PlayerAdded:Connect(function(player)
    player.Chatted:Connect(function(message)
        local code = message:match("^!nightfall%s+([%w%-]+)$")
        if code then
            pendingClaimCodes[player.UserId] = string.upper(code)
            player:Kick("Nightfall Premium code saved. Rejoin the game to finish the purchase.") -- remove this line if you do not want a rejoin flow
        end
    end)
end)

-- Players can also have the claim code set by your own UI instead of !nightfall <code>.
