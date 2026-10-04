const codes = [
    "STARR10","NF002UME7YRJ","NF00392TLD6X","NF004NF8ZSKC","NF0053UME7YR","NF006G92TLD6",
    "NF007VNF8ZSK","NF008A3UME7Y","NF009PG92TLD","NF0104VNF8ZS","NF011HA3UME7","NF012WPG92TL",
    "NF013B4VNF8Z","NF014QHA3UME","NF0155WPG92T","NF016JB4VNF8","NF017XQHA3UM","NF018C5WPG92",
    "NF019RJB4VNF","NF0206XQHA3U","NF021KC5WPG9","NF022YRJB4VN","NF023D6XQHA3","NF024SKC5WPG",
    "NF0257YRJB4V","NF026LD6XQHA","NF027ZSKC5WP","NF028E7YRJB4","NF029TLD6XQH","NF0308ZSKC5W",
    "NF031ME7YRJB","NF0322TLD6XQ","NF033F8ZSKC5","NF034UME7YRJ","NF03592TLD6X","NF036NF8ZSKC",
    "NF0373UME7YR","NF038G92TLD6","NF039VNF8ZSK","NF040A3UME7Y","NF041PG92TLD","NF0424VNF8ZS",
    "NF043HA3UME7","NF044WPG92TL","NF045B4VNF8Z","NF046QHA3UME","NF0475WPG92T","NF048JB4VNF8",
    "NF049XQHA3UM","NF050C5WPG92","NF051RJB4VNF","NF0526XQHA3U","NF053KC5WPG9","NF054YRJB4VN",
    "NF055D6XQHA3","NF056SKC5WPG","NF0577YRJB4V","NF058LD6XQHA","NF059ZSKC5WP","NF060E7YRJB4",
    "NF061TLD6XQH","NF0628ZSKC5W","NF063ME7YRJB","NF0642TLD6XQ","NF065F8ZSKC5","NF066UME7YRJ",
    "NF06792TLD6X","NF068NF8ZSKC","NF0693UME7YR","NF070G92TLD6","NF071VNF8ZSK","NF072A3UME7Y",
    "NF073PG92TLD","NF0744VNF8ZS","NF075HA3UME7","NF076WPG92TL","NF077B4VNF8Z","NF078QHA3UME",
    "NF0795WPG92T","NF080JB4VNF8","NF081XQHA3UM","NF082C5WPG92","NF083RJB4VNF","NF0846XQHA3U",
    "NF085KC5WPG9","NF086YRJB4VN","NF087D6XQHA3","NF088SKC5WPG","NF0897YRJB4V","NF090LD6XQHA",
    "NF091ZSKC5WP","NF092E7YRJB4","NF093TLD6XQH","NF0948ZSKC5W","NF095ME7YRJB","NF0962TLD6XQ",
    "NF097F8ZSKC5","NF098UME7YRJ","NF09992TLD6X","NF100NF8ZSKC"
  ];;
document.addEventListener("DOMContentLoaded",()=>{const key="nightfall-found-secrets-v2";let found=[];try{found=JSON.parse(localStorage.getItem(key)||"[]").filter(n=>Number.isInteger(n)&&n>=0&&n<100);}catch(_){}found=[...new Set(found)];const n=found.length;document.getElementById("secretsFound").textContent=n+" / 100";document.getElementById("secretsPercent").textContent=n+"%";document.getElementById("secretsDiscount").textContent=n+"%";document.getElementById("secretsRemaining").textContent=String(100-n);document.getElementById("secretsBar").style.width=n+"%";
const selectedKey="nightfall-selected-discounts-v1"; let selected=new Set(); try{selected=new Set(JSON.parse(localStorage.getItem(selectedKey)||"[]").filter(i=>Number.isInteger(i)&&i>=0&&i<100&&found.includes(i)));}catch(_){}
const list=document.getElementById("secretDiscountList"),total=document.getElementById("selectedDiscountTotal"),preview=document.getElementById("checkoutDiscountPreview");
const save=()=>localStorage.setItem(selectedKey,JSON.stringify([...selected]));
const render=()=>{if(!list)return;list.innerHTML="";found.forEach(i=>{const row=document.createElement("label");row.className="secret-discount-item";const cb=document.createElement("input");cb.type="checkbox";cb.checked=selected.has(i);cb.onchange=()=>{cb.checked?selected.add(i):selected.delete(i);save();render();};const info=document.createElement("span");info.innerHTML="<b>Easter Egg #"+String(i+1).padStart(2,"0")+"</b><small>Code: "+codes[i]+" • 1% off Premium</small>";row.append(cb,info);list.appendChild(row);});const pct=selected.size;total.textContent=pct+"%";preview.textContent=pct+"% discount selected";};
render();});