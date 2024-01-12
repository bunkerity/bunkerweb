
#define     %2%_pallocp(p,pl)                   p = %1%_palloc (pl,sizeof(*p))
#define     %2%_pallocpn(p,pl,n)                p = %1%_palloc (pl,sizeof(*p)*(n))

#define     %2%_pcallocp(p,pl)                  p = %1%_pcalloc (pl,sizeof(*p))
#define     %2%_pcallocpn(p,pl,n)               p = %1%_pcalloc (pl,sizeof(*p)*(n))
