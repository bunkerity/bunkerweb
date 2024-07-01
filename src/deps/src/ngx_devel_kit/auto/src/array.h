
#define     %2%_array_count(a)                  ((a)->nelts)
#define     %2%_array_get_first(a)              ((a)->elts)
#define     %2%_array_get_index(a,n)            ((void*) ((char*) (a)->elts + (a)->size * n))
#define     %2%_array_get_last(a)               ((void*) ((char*) (a)->elts + (a)->size * ((a)->nelts - 1)))
#define     %2%_array_get_reverse_index(a,n)    ((void*) ((char*) (a)->elts + (a)->size * ((a)->nelts - 1 - n)))
#define     %2%_array_push_clean(p,a)           {p = %1%_array_push (a); %2%_zerop (p);}
