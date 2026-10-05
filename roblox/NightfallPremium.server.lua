-- Nightfall Premium entitlement system
-- One Script: ServerScriptService/NightfallPremium
-- Full Premium pass: 1747241092 (179 Robux)
-- Arcade Premium pass: 1744202935 (70 Robux)
-- Code "started": one-time 90-day Premium entitlement

local Players = game:GetService("Players")
local MarketplaceService = game:GetService("MarketplaceService")
local DataStoreService = game:GetService("DataStoreService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HttpService = game:GetService("HttpService")

local FULL_PREMIUM_PASS_ID = 1747241092
local DISCOUNT_PREMIUM_PASS_ID = 1744202935
local STARTED_CODE = "started"
local STARTED_DURATION_SECONDS = 90 * 24 * 60 * 60
local WEBSITE_URL = "https://testiny-7wuu.onrender.com"
local PREMIUM_STORE = DataStoreService:GetDataStore("NightfallPremium_v1")

local PREMIUM_FEATURES = {
    Customization = true,
    AIFeatures = true,
    EightBall = true,
    PremiumSpaceThemes = true,
    ProfileEffects = true,
    UIColors = true,
    PremiumBadge = true,
    NameEffects = true,
    ChatEffects = true,
    ExclusivePlanetBackgrounds = true,
    PremiumDailyReward = true,
    PremiumRewards = true,
    ExtraArcadeRewards = true,
    LeaderboardBadge = true,
    PremiumTitles = true,
    EarlyAccess = true,
    Vault = true,
}

local remotes = ReplicatedStorage:FindFirstChild("NightfallPremium")
if not remotes then
    remotes = Instance.new("Folder")
    remotes.Name = "NightfallPremium"
    remotes.Parent = ReplicatedStorage
end

local function getRemote(className, name)
    local object = remotes:FindFirstChild(name)
    if object then return object end
    object = Instance.new(className)
    object.Name = name
    object.Parent = remotes
    return object
end

local redeemFunction = getRemote("RemoteFunction", "RedeemCode")
local statusFunction = getRemote("RemoteFunction", "GetStatus")
local linkFunction = getRemote("RemoteFunction", "LinkAccount")
local purchaseEvent = getRemote("RemoteEvent", "PremiumPurchase")

local cache = {}

local function loadData(userId)
    local key = "user_" .. tostring(userId)
    local ok, data = pcall(function()
        return PREMIUM_STORE:GetAsync(key)
    end)
    if not ok then
        warn("[Nightfall Premium] Could not load entitlement:", data)
        return nil
    end
    if type(data) ~= "table" then data = {} end
    return data
end

local function saveData(userId, data)
    local key = "user_" .. tostring(userId)
    local ok, err = pcall(function()
        PREMIUM_STORE:SetAsync(key, data)
    end)
    if not ok then
        warn("[Nightfall Premium] Could not save entitlement:", err)
    end
    return ok
end

local function ownsPass(userId, passId)
    local ok, owns = pcall(function()
        return MarketplaceService:UserOwnsGamePassAsync(userId, passId)
    end)
    if not ok then
        warn("[Nightfall Premium] Could not verify pass " .. tostring(passId) .. ":", owns)
        return false
    end
    return owns == true
end

local function getData(userId)
    if cache[userId] then return cache[userId] end
    local data = loadData(userId)
    if data then cache[userId] = data end
    return data
end

local function getTemporaryExpiry(data)
    local expiresAt = tonumber(data and data.premiumExpiresAt) or 0
    if expiresAt > os.time() then return expiresAt end
    return 0
end

local function getPremiumStatus(userId)
    if ownsPass(userId, FULL_PREMIUM_PASS_ID) then
        return true, "pass", 0
    end
    if ownsPass(userId, DISCOUNT_PREMIUM_PASS_ID) then
        return true, "arcade_pass", 0
    end
    local data = getData(userId)
    local expiresAt = getTemporaryExpiry(data)
    if expiresAt > 0 then
        return true, "started", expiresAt
    end
    return false, "none", 0
end

local function applyPremium(player)
    local premium, source, expiresAt = getPremiumStatus(player.UserId)
    player:SetAttribute("NightfallPremium", premium)
    player:SetAttribute("NightfallPremiumSource", source)
    player:SetAttribute("NightfallPremiumExpiresAt", expiresAt)
    for featureName, enabled in pairs(PREMIUM_FEATURES) do
        player:SetAttribute("NightfallPremium_" .. featureName, premium and enabled or false)
    end
    return premium, source, expiresAt
end

local function getBridgeSecret()
    local ok, secret = pcall(function()
        return HttpService:GetSecret("NIGHTFALL_BRIDGE_SECRET")
    end)
    if ok and secret then return secret end
    return nil
end

local function websitePost(path, body)
    local secret = getBridgeSecret()
    if not secret then
        return false, "NIGHTFALL_BRIDGE_SECRET is not configured."
    end
    local ok, response = pcall(function()
        return HttpService:RequestAsync({
            Url = WEBSITE_URL .. path,
            Method = "POST",
            Headers = {
                ["Content-Type"] = "application/json",
                ["X-Roblox-Bridge-Key"] = secret,
            },
            Body = HttpService:JSONEncode(body),
        })
    end)
    if not ok or not response.Success then
        return false, "Website request failed."
    end
    local decodedOk, decoded = pcall(function()
        return HttpService:JSONDecode(response.Body)
    end)
    if decodedOk then return true, decoded end
    return true, {}
end

local function syncPremiumToWebsite(player, premium, source, expiresAt)
    task.spawn(function()
        websitePost("/api/roblox/premium-sync", {
            roblox_user_id = tostring(player.UserId),
            premium = premium,
            premium_source = source,
            premium_expires_at = expiresAt or 0,
        })
    end)
end

local function refreshAndSync(player)
    local premium, source, expiresAt = applyPremium(player)
    syncPremiumToWebsite(player, premium, source, expiresAt)
    return premium, source, expiresAt
end

linkFunction.OnServerInvoke = function(player, rawCode)
    local code = tostring(rawCode or ""):upper():gsub("%s+", "")
    if not code:match("^[A-Z0-9%-]+$") or #code < 4 or #code > 32 then
        return { ok = false, error = "Invalid link code." }
    end
    local ok, response = websitePost("/api/roblox/link/claim", {
        roblox_user_id = tostring(player.UserId),
        link_token = code,
        code = code,
    })
    if not ok or type(response) ~= "table" or response.ok == false then
        return {
            ok = false,
            error = (type(response) == "table" and response.error) or "Could not link the account.",
        }
    end
    local premium, source, expiresAt = refreshAndSync(player)
    return { ok = true, success = true, premium = premium, source = source, expiresAt = expiresAt }
end

redeemFunction.OnServerInvoke = function(player, rawCode)
    if type(rawCode) ~= "string" then
        return { ok = false, success = false, error = "Invalid code." }
    end
    local code = string.lower(rawCode:gsub("^%s+", ""):gsub("%s+$", ""))
    if code ~= STARTED_CODE then
        return { ok = false, success = false, error = "Invalid code." }
    end

    local data = getData(player.UserId)
    if not data then
        return { ok = false, success = false, error = "Premium service is temporarily unavailable." }
    end
    if data.startedRedeemed == true then
        return { ok = false, success = false, error = "This code has already been redeemed on your account." }
    end

    local now = os.time()
    data.startedRedeemed = true
    data.startedRedeemedAt = now
    data.premiumExpiresAt = now + STARTED_DURATION_SECONDS
    data.premiumSource = "started"

    if not saveData(player.UserId, data) then
        return { ok = false, success = false, error = "Could not save the Premium entitlement. Try again." }
    end

    cache[player.UserId] = data
    local premium, source, expiresAt = refreshAndSync(player)

    return {
        ok = premium,
        success = premium,
        source = source,
        expiresAt = expiresAt,
        message = "3 months of Premium have been added to your account.",
        vaultUnlocked = premium,
    }
end

statusFunction.OnServerInvoke = function(player)
    local premium, source, expiresAt = refreshAndSync(player)
    local data = getData(player.UserId)
    return {
        premium = premium,
        source = source,
        expiresAt = expiresAt,
        startedRedeemed = data and data.startedRedeemed == true or false,
        vaultUnlocked = premium,
        arcadeOfferUnlocked = false,
        features = PREMIUM_FEATURES,
    }
end

Players.PlayerAdded:Connect(function(player)
    task.spawn(function()
        refreshAndSync(player)
    end)
end)

Players.PlayerRemoving:Connect(function(player)
    cache[player.UserId] = nil
end)

for _, player in ipairs(Players:GetPlayers()) do
    task.spawn(function()
        refreshAndSync(player)
    end)
end

MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(player, gamePassId, purchased)
    if not purchased then return end
    if gamePassId == FULL_PREMIUM_PASS_ID or gamePassId == DISCOUNT_PREMIUM_PASS_ID then
        local premium, source, expiresAt = refreshAndSync(player)
        purchaseEvent:FireClient(player, {
            success = premium,
            premium = premium,
            source = source,
            expiresAt = expiresAt,
            vaultUnlocked = premium,
        })
    end
end)

task.spawn(function()
    while true do
        task.wait(60)
        for _, player in ipairs(Players:GetPlayers()) do
            local premium, source, expiresAt = applyPremium(player)
            if source == "started" or not premium then
                syncPremiumToWebsite(player, premium, source, expiresAt)
            end
        end
    end
end)

print("[Nightfall Premium] One-file server system loaded.")
